from kiwipiepy import Kiwi
from kiwipiepy.utils import Stopwords

stopwords = Stopwords()
kiwi = Kiwi(model_type="sbg")

if __name__ == "__main__":
    query = "안녕하세요. 반갑습니다."

    # kiwi 사용해서 토크나이징
    tokenized_text = [' '.join([token.form for token in tokens]) for tokens in
                      kiwi.tokenize([query], stopwords=stopwords)]

    print(tokenized_text)