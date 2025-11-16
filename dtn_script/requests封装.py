import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging


class HttpClient:
    """
    一个可复用的 HTTP 请求客户端封装
    - 支持 Session
    - 支持默认 Header
    - 支持代理
    - 支持 hooks
    - 自动重试机制
    """

    def __init__(self, base_url=None, default_headers=None, proxies=None, timeout=10, retries=3, backoff_factor=0.3):
        """
        初始化 HttpClient

        :param base_url: 基础 URL，可省略
        :param default_headers: 默认请求头（dict）
        :param proxies: 代理设置（dict）
        :param timeout: 每次请求的超时时间
        :param retries: 重试次数
        :param backoff_factor: 重试退避系数
        """

        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout = timeout
        self.session = requests.Session()

        # 设置默认 headers（Session 将继承这些）
        if default_headers:
            self.session.headers.update(default_headers)

        # 设置代理
        if proxies:
            self.session.proxies.update(proxies)

        # 配置重试机制（对 GET / POST 都可用）
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 启用日志记录，便于排查问题
        self.logger = logging.getLogger("HttpClient")

    # -------------------------
    # headers 相关管理函数
    # -------------------------
    def set_header(self, key, value):
        """设置（覆盖）一个默认请求头"""
        self.session.headers[key] = value

    def remove_header(self, key):
        """清除指定 header"""
        if key in self.session.headers:
            del self.session.headers[key]

    def clear_headers(self):
        """彻底清空 session 默认请求头"""
        self.session.headers.clear()

    # -------------------------
    # 核心请求方法
    # -------------------------
    def request(self, method, url, **kwargs):
        """
        通用请求入口，基础封装

        :param method: HTTP 方法（GET/POST/PUT/DELETE/PATCH/HEAD）
        :param url: 完整或相对 URL
        :param kwargs: requests 支持的所有参数，例如 json、params、data、headers...
        """

        full_url = f"{self.base_url}{url}" if self.base_url and not url.startswith("http") else url

        # 默认超时
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        # 请求前日志
        self.logger.debug(f"[HTTP {method}] URL: {full_url} | KWARGS: {kwargs}")

        try:
            response = self.session.request(method, full_url, **kwargs)

            # 自动检查状态码
            response.raise_for_status()

            return response

        except requests.exceptions.RequestException as e:
            self.logger.error(f"[HttpClient ERROR] {e}")
            raise

    # -------------------------
    # 各种 HTTP 方法封装
    # -------------------------
    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)

    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)

    # -------------------------
    # hook 使用示例封装
    # -------------------------
    def request_with_hook(self, url, hook_fn, method="GET", **kwargs):
        """
        使用响应 hook 的示例

        hook_fn 必须是函数：hook_fn(response, *args, **kwargs)
        """

        def response_hook(response, *args, **kwargs):
            return hook_fn(response)

        if "hooks" not in kwargs:
            kwargs["hooks"] = {"response": response_hook}
        else:
            kwargs["hooks"]["response"] = response_hook

        return self.request(method, url, **kwargs)


# -------------------------
# ✅ 使用案例
# -------------------------
if __name__ == "__main__":

    def hook_example(resp):
        print("Hook called! URL =", resp.url)
        print("Status =", resp.status_code)

    client = HttpClient(
        base_url="https://httpbin.org",
        default_headers={"User-Agent": "MyTestClient 1.0", "aaa": "bbb"},
        proxies=None,  # 或 {"http": "http://127.0.0.1:8888"}
        timeout=5
    )

    # 普通 GET 示例
    resp = client.get("/get", params={"x": 123})
    print(resp.json())

    # 清空 headers
    client.clear_headers()

    # 设置单个 header
    client.set_header("token", "abc123")

    # POST JSON 示例
    resp = client.post("/post", json={"name": "test"})
    print(resp.json())

    # Hook 示例
    client.request_with_hook("/get", hook_example)