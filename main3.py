import re
from typing import Any, List


# ---------- JSONPath 分词器 ----------
def parse_json_path(path: str):
    tokens = []
    i = 0
    while i < len(path):
        if path[i] == '$':
            tokens.append(('$',))
            i += 1
        elif path.startswith('..', i):
            i += 2
            if i < len(path) and path[i] not in '.[':
                j = i
                while j < len(path) and path[j] not in '.[':
                    j += 1
                tokens.append(('..field', path[i:j]))
                i = j
            else:
                tokens.append(('..',))
        elif path[i] == '.':
            i += 1
            j = i
            while j < len(path) and path[j] not in '.[':
                j += 1
            tokens.append(('field', path[i:j]))
            i = j
        elif path[i] == '[':
            if path.startswith('[*]', i):
                tokens.append(('*',))
                i += 3
            elif path.startswith('[?', i):
                j = path.find(']', i)
                expr = path[i + 2:j].strip()
                tokens.append(('filter', expr))
                i = j + 1
            elif ':' in path[i:]:
                j = path.find(']', i)
                slice_expr = path[i + 1:j]
                tokens.append(('slice', slice_expr))
                i = j + 1
            else:
                j = path.find(']', i)
                index_expr = path[i + 1:j].strip("'\"")
                tokens.append(('index', index_expr))
                i = j + 1
        else:
            raise ValueError(f"Invalid JSONPath at position {i}: {path[i:]}")
    return tokens


# ---------- 过滤器表达式求值器 ----------
def evaluate_filter(expr: str, node: Any) -> bool:
    # 修改正则表达式，支持单引号和双引号包裹的字符串
    # r'@\.([\w_]+)\s+contains\s+(["\'])([^"\']+)\2'：这个正则表达式支持匹配双引号或单引号包裹的字符串。具体来说：
    #
    # (["\'])：匹配单引号或双引号，并捕获它。
    #
    # ([^"\']+)：匹配被引号包裹的内容（忽略引号本身）。
    #
    # \2：确保匹配的结束引号与开始引号相同（即如果开始是双引号，则结束也必须是双引号；如果开始是单引号，则结束必须是单引号）。
    expr = re.sub(
        r'@\.([\w_]+)\s+contains\s+(["\'])([^"\']+)\2',
        lambda m: f'"{m.group(3)}" in str(node.get("{m.group(1)}", ""))',
        expr
    )

    # 替换 @.field 为 node.get("field", "")，确保返回字符串类型
    expr = re.sub(r'@\.([\w_]+)', lambda m: f'node.get("{m.group(1)}", "")', expr)

    # 替换逻辑运算符
    expr = expr.replace("&&", "and").replace("||", "or")

    try:
        # 使用 eval 计算表达式
        return bool(eval(expr, {"node": node}))
    except Exception as e:
        print(f"错误：评估表达式失败: {expr}，节点：{node}，错误信息：{e}")
        return False


# ---------- JSONPath 执行器 ----------
def extract(json_obj: Any, path: str) -> List[Any]:
    tokens = parse_json_path(path)
    result = [json_obj]

    for token in tokens:
        next_result = []
        if token == ("$",):
            continue
        elif token == ("*",):
            for node in result:
                if isinstance(node, dict):
                    next_result.extend(node.values())
                elif isinstance(node, list):
                    for item in node:
                        next_result.append(item)
        elif token == ("..",):
            def descend(obj):
                results = []
                if isinstance(obj, dict):
                    for v in obj.values():
                        results.append(v)
                        results.extend(descend(v))
                elif isinstance(obj, list):
                    for item in obj:
                        results.extend(descend(item))
                return results

            new_result = []
            for node in result:
                new_result.extend(descend(node))
            result = new_result
            continue
        elif token[0] == "field":
            key = token[1]
            for node in result:
                if isinstance(node, dict) and key in node:
                    next_result.append(node[key])
        elif token[0] == "..field":
            key = token[1]

            def find_key_recursively(obj):
                matches = []
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == key:
                            matches.append(v)
                        matches.extend(find_key_recursively(v))
                elif isinstance(obj, list):
                    for item in obj:
                        matches.extend(find_key_recursively(item))
                return matches

            new_result = []
            for node in result:
                new_result.extend(find_key_recursively(node))
            result = new_result
            continue
        elif token[0] == "index":
            key = token[1]
            for node in result:
                if isinstance(node, dict) and key in node:
                    next_result.append(node[key])
                elif isinstance(node, list):
                    try:
                        idx = int(key)
                        next_result.append(node[idx])
                    except:
                        pass
        elif token[0] == "slice":
            start, end = token[1].split(":")
            start = int(start) if start else None
            end = int(end) if end else None
            for node in result:
                if isinstance(node, list):
                    next_result.extend(node[start:end])
        elif token[0] == "filter":
            expr = token[1]
            for node in result:
                if isinstance(node, list):
                    for item in node:
                        if evaluate_filter(expr, item):
                            next_result.append(item)
        result = next_result
    return result


if __name__ == "__main__":
    data = {
        "store": {
            "book": [
                {"category": "reference", "author": "Nigel Rees", "price": 8.95},
                {"category": "fiction", "author": "Evelyn Waugh", "price": 12.99},
                {"category": "fiction", "author": "Herman Melville", "price": 8.99},
                {"category": "fiction", "author": "J. R. R. Tolkien", "price": 22.99}
            ],
            "bicycle": {"color": "red", "price": 19.95}
        }
    }

    print("书的作者:", extract(data, "$.store.book[*].author"))
    print("所有author:", extract(data, "$..author"))
    print("store子节点:", extract(data, "$.store"))
    print("第一本书:", extract(data, "$.store.book[2].price"))
    print("第二到第三本书:", extract(data, "$.store.book[1:3].price"))

    print("字段包含:", extract(data, "$.store.book[?(@.author contains 'Tolkien')]"))
    print("字段包含:", extract(data, "$.store.book[?(@.author contains \"Tolkien\")]"))
    print("字段相等:", extract(data, "$.store.book[?(@.category == \"reference\")]"))
    print("价格小于10:", extract(data, "$.store.book[?(@.price < 10)]"))
    print("多条件:", extract(data, "$.store.book[?(@.price < 10 && @.category == 'reference')]"))
    print("多条件:", extract(data, "$.store.book[?(@.price > 500 || @.category == 'fiction')]"))
