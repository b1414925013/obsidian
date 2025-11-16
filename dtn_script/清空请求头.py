import requests

# 创建一个 Session 对象
session = requests.Session()

# 设置默认请求头
session.headers.update({'aaa': 'bbb', 'User-Agent': 'my-app/1.0'})

# 打印当前的请求头
print("Before deletion:", session.headers)

# 删除特定的请求头 'aaa'
if 'aaa' in session.headers:
    del session.headers['aaa']

# 打印删除后的请求头
print("After deletion:", session.headers)


# 创建一个 Session 对象
session = requests.Session()

# 设置默认请求头
session.headers.update({'aaa': 'bbb', 'User-Agent': 'my-app/1.0'})

# 打印当前的请求头
print("Before clearing:", session.headers)

# 清空所有请求头
session.headers.clear()

# 打印清空后的请求头
print("After clearing:", session.headers)

