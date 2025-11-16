class FileUploadClient(HttpClient):
    """继承你的 HttpClient，扩展文件上传功能"""

    def upload_file(self, url, file_path, field_name="file", extra_data=None, **kwargs):
        """
        小文件上传
        :param url: 上传地址
        :param file_path: 文件路径
        :param field_name: form-data 中的 name 字段
        :param extra_data: 附带额外字段
        """

        files = {
            field_name: open(file_path, "rb")
        }

        data = extra_data or {}

        return self.post(url, files=files, data=data, **kwargs)


class ChunkUploader(HttpClient):

    def upload_in_chunks(self, url, file_path, chunk_size=10 * 1024 * 1024, progress_callback=None, **kwargs):
        """
        大文件分块上传

        :param url: 上传接口
        :param file_path: 文件路径
        :param chunk_size: 每块大小（默认 10MB）
        :param progress_callback: 回调函数(progress, total)
        """

        file_size = os.path.getsize(file_path)
        uploaded = 0

        with open(file_path, "rb") as f:
            chunk_index = 0

            while True:
                data = f.read(chunk_size)
                if not data:
                    break

                files = {
                    "file": (f"chunk_{chunk_index}", data)
                }

                resp = self.post(url, files=files, **kwargs)

                uploaded += len(data)

                if progress_callback:
                    progress_callback(uploaded, file_size)

                chunk_index += 1

        return {"status": "ok", "total_size": file_size}
import os

def progress(uploaded, total):
    print(f"{uploaded}/{total} bytes uploaded ({uploaded/total*100:.2f}%)")

uploader = ChunkUploader(base_url="https://httpbin.org")

result = uploader.upload_in_chunks(
    "/post",
    file_path="bigfile.bin",
    progress_callback=progress
)

print(result)
