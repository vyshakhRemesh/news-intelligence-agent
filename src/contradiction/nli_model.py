from transformers import pipeline


class NLIModel:

    def __init__(self):

        self.classifier = pipeline(
            "text-classification",
            model="facebook/bart-large-mnli"
        )

    def predict(self, text1, text2):

        result = self.classifier(
            {
                "text": text1,
                "text_pair": text2
            }
        )

        return result