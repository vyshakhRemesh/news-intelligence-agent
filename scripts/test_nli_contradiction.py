from src.contradiction.nli_model import NLIModel


def main():
    model = NLIModel()

    statement_1 = (
        "The company reported a profit of 10 million pounds "
        "during the first quarter."
    )

    statement_2 = (
        "The company reported a loss of 10 million pounds "
        "during the first quarter."
    )

    result = model.predict(statement_1, statement_2)

    print("Statement 1:", statement_1)
    print("Statement 2:", statement_2)
    print("Prediction:", result)


if __name__ == "__main__":
    main()