class ResponseBuilder:

    @staticmethod
    def success(
        message,
        data=None
    ):

        return {
            "success": True,
            "message": message,
            "data": data
        }


    @staticmethod
    def error(message):

        return {
            "success": False,
            "message": message
        }