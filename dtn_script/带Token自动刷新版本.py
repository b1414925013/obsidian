import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time


class TokenHttpClient:
    """
    支持自动刷新 Token 的 HTTP 请求封装
    """

    def __init__(self,
                 base_url=None,
                 get_token_func=None,
                 refresh_token_func=None,
                 auto_update_headers=True,
                 retries=3,
                 backoff_factor=0.3):

        self.base_url = base_url.rstrip("/") if base_url else None
        self.session = requests.Session()

        # token 获取与刷新逻辑
        self.get_token_func = get_token_func
        self.refresh_token_func = refresh_token_func
        self.auto_update_headers = auto_update_headers

        # 初始化 token
        if self.get_token_func:
            self.token = self.get_token_func()
        else:
            self.token = None

        # 启用 token 头
        if self.auto_update_headers and self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

        # 重试策略
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def update_token_header(self):
        """更新 Authorization header"""
        if self.auto_update_headers and self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def refresh_token(self):
        """刷新 token（调用用户提供的函数）"""
        if not self.refresh_token_func:
            raise Exception("No refresh_token_func provided!")

        new_token = self.refresh_token_func()
        if not new_token:
            raise Exception("refresh token failed!")

        self.token = new_token
        self.update_token_header()

    def request(self, method, url, retry_on_401=True, **kwargs):
        """封装请求逻辑并支持自动刷新 token"""

        full_url = f"{self.base_url}{url}" if self.base_url and not url.startswith("http") else url

        response = self.session.request(method, full_url, timeout=10, **kwargs)

        # token 失效自动刷新
        if response.status_code == 401 and retry_on_401:
            print("Token expired, refreshing...")
            self.refresh_token()

            # 再次请求
            response = self.session.request(method, full_url, timeout=10, **kwargs)

        response.raise_for_status()
        return response

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


if __name__ == '__main__':
    # 模拟 token 生成
    def get_token():
        return "token123"


    # 模拟 token 刷新
    def refresh_token():
        print("Calling refresh_token API...")
        return "new_token_456"


    client = TokenHttpClient(
        base_url="https://httpbin.org",
        get_token_func=get_token,
        refresh_token_func=refresh_token,
    )

    # 自动附带 token
    resp = client.get("/get")
    print(resp.json())

    # 模拟 401 自动刷新
    # resp = client.get("/status/401")