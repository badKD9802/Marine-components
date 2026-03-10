import json


class Util:
    # def __init__(self):
    #     self.client = OpenAI(base_url='http://210.116.106.101:3006/v1', api_key='???')

    # def generate_text(self,prompt):
    #     """
    #     Calls the OpenAI API to generate a response based on the provided prompt.
    #     It also handles a model-specific closing tag to clean the output.
    #     """
    #     completion = self.client.chat.completions.create( #  101서버, Qwen3-8b
    #         model="/mnt/model",
    #         messages=[{"role": "user", "content": prompt}],
    #         temperature=0,
    #         max_tokens=2048,
    #         extra_body={
    #             "chat_template_kwargs": {"enable_thinking": False},
    #         },
    #     )
    #     response = completion.choices[0].message.content

    #     # Qwen3-specific logic to remove the closing tag if present; Qwen3 리즈닝 태그 전용
    #     closing_tag = "</think>"
    #     tag_end_position = response.find(closing_tag)
    #     if tag_end_position != -1:
    #         string_after_tag = response[tag_end_position + len(closing_tag):]
    #         return string_after_tag.strip()

    #     return response.strip()

    def json_replace(self, result: str) -> dict:
        try:
            cleaned_result = result.replace("```json", "").replace("```", "").strip()
            if not cleaned_result:
                return {"result": "error_empty_response"}
            response = json.loads(cleaned_result)
            return response
        except json.JSONDecodeError:
            print(f"Warning: Failed to decode JSON from response: {result}")
            return {"result": "error_invalid_json"}


# 전역 인스턴스
util = Util()
