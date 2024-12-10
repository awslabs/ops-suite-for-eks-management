import string


class CaseConverter:

    @staticmethod
    def to_camel(pascal_case_str: str) -> str:
        if pascal_case_str is None or len(pascal_case_str) == 0:
            return ""

        pascal_case_str = pascal_case_str.strip()

        if pascal_case_str.isupper() or pascal_case_str.isnumeric():
            return pascal_case_str

        return pascal_case_str[0].lower() + pascal_case_str[1:]

    @staticmethod
    def to_pascal(camel_case_str: str) -> str:
        if camel_case_str is None or len(camel_case_str) == 0:
            return ""

        camel_case_str = camel_case_str.strip()

        if camel_case_str.isupper() or camel_case_str.isnumeric():
            return camel_case_str

        return string.capwords(camel_case_str)

    @staticmethod
    def pascal_to_camel(body: dict | list) -> dict | list:
        if type(body) is list:
            temp = []
            for item in body:
                temp.append(CaseConverter.pascal_to_camel(item))

            return temp

        if type(body) is dict:
            temp = {}
            for key in body.keys():
                content = body[key]
                new_key = CaseConverter.to_camel(key)
                temp[new_key] = content

                new_list = []
                if type(content) is list:
                    for i in content:
                        if type(i) is dict:
                            new_list.append(CaseConverter.pascal_to_camel(i))

                    if len(new_list) != 0:
                        temp[new_key] = new_list

                if type(content) is dict:
                    temp[new_key] = CaseConverter.pascal_to_camel(content)

            return temp

    @staticmethod
    def camel_to_pascal(body: dict | list) -> dict | list:
        if type(body) is list:
            temp = []
            for item in body:
                temp.append(CaseConverter.pascal_to_camel(item))

            return temp

        if type(body) is dict:
            temp = {}
            for key in body.keys():
                content = body[key]
                new_key = CaseConverter.to_pascal(key)
                temp[new_key] = content

                new_list = []
                if type(content) is list:
                    for i in content:
                        if type(i) is dict:
                            new_list.append(CaseConverter.pascal_to_camel(i))

                    if len(new_list) != 0:
                        temp[new_key] = new_list

                if type(content) is dict:
                    temp[new_key] = CaseConverter.pascal_to_camel(content)

            return temp
