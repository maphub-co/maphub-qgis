class APIException(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)