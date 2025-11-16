"""
ssh_bastion_refactor.py

功能：
- 提供两个变体：
  1) run_remote_cmd_via_bastion_single_ssh()：
     在跳板机上执行单条 SSH 命令，命令格式类似：
       ssh paas@192.168.0.7 'docker exec container ls'
     脚本会对单引号进行正确转义，并会在必要时自动应答 password/host-key 确认提示。
     这是你要求的“非交互版本 -> 通过跳板直接执行单条 shell（单引号包装）”的等价实现。

  2) run_commands_via_bastion_interactive_improved()：
     基于之前的交互式实现，但提示检测更稳健（支持多语言 password 提示等）。
     仍然会在跳板上打开交互 shell、ssh 到目标、docker exec -it 进入容器，
     并在容器内执行用户命令（使用 marker 捕获输出）。

注意：
- 示例中包含明文密码，仅供测试/受控环境使用。生产请用密钥或Secret管理器。
- 交互式行为依赖远端提示文字；不同系统/语言可能需要微调正则。
"""

import paramiko
import time
import re
from typing import Tuple, Optional, List

# ----------------------------
# 配置示例（请按需修改）
# ----------------------------
JUMP_HOST = "10.236.7.8"
JUMP_PORT = 22
JUMP_USER = "username"
JUMP_PASS = "password"

TARGET_HOST = "192.168.0.7"
TARGET_USER = "paas"
TARGET_PASS = "123456"

CONTAINER = "xxxx"
CONTAINER_SHELL = "/bin/bash"
FILE_TO_CAT = "/aaa/bbb"

DEFAULT_TIMEOUT = 30.0

# ----------------------------
# 公共工具函数
# ----------------------------

def clean_ansi(s: str) -> str:
    """移除 ANSI 控制码（颜色/控制字符）"""
    return re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', s)

def recv_all(channel: paramiko.Channel, timeout: float = 0.5) -> str:
    """
    从 channel 非阻塞读取可用数据，等待 timeout 秒无新数据则返回。
    用于交互式 shell。
    """
    out = []
    start = time.time()
    while True:
        if channel.recv_ready():
            chunk = channel.recv(65536)
            if not chunk:
                break
            out.append(chunk.decode('utf-8', errors='ignore'))
            # 短暂等待更多数据
            time.sleep(0.01)
            start = time.time()
        else:
            if time.time() - start > timeout:
                break
            time.sleep(0.01)
    return ''.join(out)

def wait_for_patterns(channel: paramiko.Channel, patterns: List[str], timeout: float = DEFAULT_TIMEOUT) -> Tuple[Optional[str], str]:
    """
    在 channel 输出中等待任一 pattern（正则，忽略大小写）。
    返回 (matched_pattern_or_None, buffer)
    """
    buf = ""
    end_time = time.time() + timeout
    while time.time() < end_time:
        buf += recv_all(channel, timeout=0.5)
        for pat in patterns:
            if re.search(pat, buf, flags=re.IGNORECASE):
                return pat, buf
        time.sleep(0.05)
    return None, buf

def connect_bastion(host: str, port: int, username: str, password: str, timeout: float = 10) -> paramiko.SSHClient:
    """
    连接跳板机 (username/password)，返回已连接的 SSHClient。
    自动 accept hostkey（AutoAddPolicy），便于脚本化。
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=username, password=password,
                   look_for_keys=False, allow_agent=False, timeout=timeout)
    return client

# ----------------------------
# 辅助：将远程命令包裹在单引号中并对内部单引号进行转义
# ----------------------------
def single_quote_wrap_and_escape(cmd: str) -> str:
    """
    将 cmd 用单引号包装并正确转义内部单引号，生成 shell-safe 的单引号包裹字符串。
    方法：在单引号内部出现的单引号需替换为: '\''  （shell 标准转义方式）
    例： O'Reilly -> 'O'\''Reilly'
    """
    # 替换所有单引号为 '\'' 序列
    escaped = cmd.replace("'", "'\\''")
    return f"'{escaped}'"

# ----------------------------
# 非交互（简化 single-ssh）版本
# 在跳板机上运行：ssh target_user@target_host 'remote_cmd'
# 如果目标要求密码，将自动在跳板的 channel 上响应 password 提示
# ----------------------------
def run_remote_cmd_via_bastion_single_ssh(
        jump_host: str, jump_port: int, jump_user: str, jump_pass: str,
        target_user: str, target_host: str, target_pass: str,
        remote_cmd: str,
        timeout: float = DEFAULT_TIMEOUT) -> Tuple[str, str]:
    """
    在跳板机上执行一条 ssh 到目标并运行 remote_cmd 的命令（remote_cmd 将被单引号包裹并转义）。
    返回 (stdout_full, stderr_full) —— 注意：在 invoke_shell 模式下，stderr 可能混在 stdout 中。
    实现细节：
      - 在跳板上打开一个带 pty 的 session（invoke_shell），发送完整的 ssh 命令：
          ssh paas@192.168.0.7 'docker exec container ls'
      - 监听常见提示（包括多语言 password、host-key 确认），并自动发送回答。
      - 捕获并返回执行输出（清理 ANSI 控制码）。
    备注：这种方式最接近 `ssh -J jump user@target 'cmd'` 的单行行为。
    """
    bastion = None
    channel = None
    try:
        bastion = connect_bastion(jump_host, jump_port, jump_user, jump_pass)
        transport = bastion.get_transport()
        if transport is None:
            raise RuntimeError("Bastion transport is None")

        channel = transport.open_session()
        channel.get_pty()
        channel.invoke_shell()
        time.sleep(0.1)

        # 清空初始信息
        _ = recv_all(channel, timeout=0.2)

        # 构造 ssh 命令，远程 cmd 用单引号包裹并转义
        remote_wrapped = single_quote_wrap_and_escape(remote_cmd)
        ssh_cmd = f"ssh {target_user}@{target_host} {remote_wrapped}"
        channel.send(ssh_cmd + "\n")

        # 多语言 password / host-key patterns 列表（交互式自动应答用）
        password_patterns = [
            r"password[:\s]*$",    # English
            r"密码[:\s]*$",         # Chinese
            r"contraseña[:\s]*$",  # Spanish
            r"mot de passe[:\s]*$",# French
            r"senha[:\s]*$",       # Portuguese
            r"パスワード[:\s]*$",   # Japanese
            r"パスワード",          # Japanese fallback
            r"passwd[:\s]*$",      # passwd
        ]
        hostkey_patterns = [
            r"are you sure you want to continue connecting",  # typical english
            r"yes/no",                                       # yes/no prompt
            r"是否继续连接",                                    # Chinese-ish (not standard but defensive)
        ]
        error_patterns = [
            r"permission denied",
            r"No such file or directory",
            r"Connection refused",
            r"Could not resolve hostname",
        ]

        # 合并等待模式（优先级： password/hostkey/error/prompt end）
        patterns = password_patterns + hostkey_patterns + error_patterns + [r"\$ ", r"# "]

        # 读取并在需要时回应
        overall_buf = ""
        while True:
            pat, buf = wait_for_patterns(channel, patterns, timeout=20.0)
            overall_buf += buf
            # 如果没有匹配，超时退出循环（可能命令已完成）
            if pat is None:
                break
            pat_low = pat.lower()
            # check hostkey confirmation
            if re.search(r"are you sure you want to continue connecting|yes/no", pat, flags=re.IGNORECASE):
                channel.send("yes\n")
                time.sleep(0.2)
                continue
            # check password patterns (多语言)
            if any(re.search(pp, pat, flags=re.IGNORECASE) for pp in password_patterns):
                # 发送目标密码
                channel.send(target_pass + "\n")
                time.sleep(0.5)
                continue
            # check errors
            if any(re.search(ep, pat, flags=re.IGNORECASE) for ep in error_patterns):
                # 捕获错误后继续读取剩余输出然后退出
                time.sleep(0.2)
                break
            # 如果匹配到 shell prompt ($ / #) 说明命令完成或进入 shell
            if re.search(r"\$ |# ", pat):
                # 读取后续输出然后退出
                time.sleep(0.2)
                break

        # 给远程命令一些时间输出并读取全部缓冲
        time.sleep(0.5)
        final = recv_all(channel, timeout=1.0)
        overall_buf += final

        # 清理并返回
        overall_buf = clean_ansi(overall_buf)
        # 尝试把 stdout/stderr 分离并返回 stderr as empty (因为通过 shell 难以精确分离)
        return overall_buf, ""
    finally:
        if channel:
            try:
                channel.close()
            except Exception:
                pass
        if bastion:
            try:
                bastion.close()
            except Exception:
                pass


# ----------------------------
# 交互式版本（改进提示检测）
# - 支持多语言 password 提示列表
# - 支持更稳健的 host-key 确认检测
# ----------------------------
def run_commands_via_bastion_interactive_improved(
        jump_host: str, jump_port: int, jump_user: str, jump_pass: str,
        target_host: str, target_user: str, target_pass: str,
        container: str, container_shell: str,
        list_of_commands_inside_container: List[str],
        timeout: float = DEFAULT_TIMEOUT) -> List[str]:
    """
    在跳板机上打开交互式 shell -> ssh 目标 -> docker exec -it 进入容器（或直接在目标 shell 执行容器命令）；
    在容器内执行 list_of_commands_inside_container（例如 ['ls', 'cat /aaa/bbb']），
    对常见提示（多语言 password、host-key 确认）做自动应答。
    返回每条命令对应的原始输出（列表，已经去掉 ANSI）。
    """
    bastion = None
    channel = None
    try:
        bastion = connect_bastion(jump_host, jump_port, jump_user, jump_pass)
        transport = bastion.get_transport()
        if transport is None:
            raise RuntimeError("No transport from bastion")

        channel = transport.open_session()
        channel.get_pty()
        channel.invoke_shell()
        time.sleep(0.1)
        # 清初始内容
        _ = recv_all(channel, timeout=0.2)

        send = lambda s: channel.send(s + ("\n" if not s.endswith("\n") else ""))

        # 1) ssh 到目标主机
        send(f"ssh {target_user}@{target_host}")

        # 更长、更全面的多语言提示集
        password_patterns = [
            r"password[:\s]*$", r"密码[:\s]*$", r"contraseña[:\s]*$", r"mot de passe[:\s]*$",
            r"senha[:\s]*$", r"パスワード[:\s]*$", r"passwd[:\s]*$"
        ]
        hostkey_patterns = [
            r"are you sure you want to continue connecting", r"yes/no", r"是否继续连接", r"continuar conectando"
        ]
        generic_prompts = [r"\$ ", r"# ", r"% "]  # 常见 shell prompt 尾
        error_patterns = [r"permission denied", r"connection refused", r"no route to host"]

        patterns = password_patterns + hostkey_patterns + error_patterns + generic_prompts

        # 等待并响应 ssh 登录过程
        while True:
            pat, buf = wait_for_patterns(channel, patterns, timeout=15.0)
            if pat is None:
                # 超时：检查缓冲是否显示已在目标 shell（例如 prompt / user@host）
                # 尝试从 buf 中判断
                if re.search(rf"{re.escape(target_user)}@{re.escape(target_host)}", buf):
                    break
                # 若实际已有 shell 提示，则继续
                if re.search(r"\$ |# ", buf):
                    break
                raise RuntimeError("Timeout while ssh to target; buffer:\n" + clean_ansi(buf[-2000:]))
            # 处理 hostkey 确认
            if re.search(r"are you sure you want to continue connecting|yes/no|是否继续连接", pat, flags=re.IGNORECASE):
                send("yes")
                time.sleep(0.2)
                continue
            # 处理多语言密码提示
            if any(re.search(pp, pat, flags=re.IGNORECASE) for pp in password_patterns):
                send(target_pass)
                time.sleep(0.5)
                continue
            # 检查错误
            if any(re.search(ep, pat, flags=re.IGNORECASE) for ep in error_patterns):
                raise RuntimeError("SSH error during login: " + clean_ansi(buf[-2000:]))
            # 如果出现 shell prompt，则登录成功
            if re.search(r"\$ |# |% ", buf):
                break

        # 清空缓冲
        time.sleep(0.1)
        _ = recv_all(channel, timeout=0.2)

        # 2) 执行 docker exec -it <container> <container_shell>
        send(f"docker exec -it {container} {container_shell}")

        # docker exec 可能会直接进入容器的 shell 或报错或出现密码提示（少见）
        patterns2 = password_patterns + hostkey_patterns + error_patterns + generic_prompts
        while True:
            pat, buf = wait_for_patterns(channel, patterns2, timeout=15.0)
            if pat is None:
                # 可能已进入容器 shell，继续
                break
            if re.search(r"are you sure you want to continue connecting|yes/no", pat, flags=re.IGNORECASE):
                send("yes")
                time.sleep(0.2)
                continue
            if any(re.search(pp, pat, flags=re.IGNORECASE) for pp in password_patterns):
                send(target_pass)
                time.sleep(0.5)
                continue
            if re.search(r"No such container|Error response from daemon", buf, flags=re.IGNORECASE):
                raise RuntimeError("docker exec failed: " + clean_ansi(buf))
            if re.search(r"\$ |# |% ", buf):
                break

        # 清空缓冲
        time.sleep(0.1)
        _ = recv_all(channel, timeout=0.2)

        # 3) 在容器内执行命令并用 marker 捕获输出
        outputs = []
        for i, cmd in enumerate(list_of_commands_inside_container):
            marker = f"__CMD_END_{i}__"
            send(f"{cmd}; echo {marker}")
            pat, buf = wait_for_patterns(channel, [re.escape(marker), ] + password_patterns + hostkey_patterns, timeout=20.0)
            if pat is None:
                outputs.append(clean_ansi(buf))
            else:
                outputs.append(clean_ansi(buf))
            time.sleep(0.05)

        return outputs

    finally:
        if channel:
            try:
                channel.close()
            except Exception:
                pass
        if bastion:
            try:
                bastion.close()
            except Exception:
                pass


# ----------------------------
# 使用示例（脚本入口）
# ----------------------------
if __name__ == "__main__":
    # 示例：非交互简化 single-ssh（在跳板执行 ssh 'cmd'）
    try:
        print("=== 非交互（单条 ssh 命令在跳板上执行）示例 ===")
        # 本例要执行的远程命令，注意：不要自己再手动加外层单引号，库会处理
        remote_command = f"docker exec {CONTAINER} ls"
        out, err = run_remote_cmd_via_bastion_single_ssh(
            JUMP_HOST, JUMP_PORT, JUMP_USER, JUMP_PASS,
            TARGET_USER, TARGET_HOST, TARGET_PASS,
            remote_command
        )
        print("== OUTPUT ==\n", out)
        if err:
            print("== ERR ==\n", err)
    except Exception as e:
        print("非交互 single-ssh 示例出错：", str(e))

    # 示例：交互式（更稳健的提示检测）
    try:
        print("\n=== 交互式（更稳健提示检测）示例 ===")
        outputs = run_commands_via_bastion_interactive_improved(
            JUMP_HOST, JUMP_PORT, JUMP_USER, JUMP_PASS,
            TARGET_HOST, TARGET_USER, TARGET_PASS,
            CONTAINER, CONTAINER_SHELL,
            ['ls', f'cat {FILE_TO_CAT}']
        )
        for i, out in enumerate(outputs):
            print(f"\n--- CMD {i} OUTPUT ---\n{out}")
    except Exception as e:
        print("交互式 示例出错：", str(e))