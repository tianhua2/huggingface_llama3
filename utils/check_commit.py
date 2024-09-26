import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_commit", type=str, required=True, help="The starting commit hash.")
    parser.add_argument("--end_commit", type=str, required=True, help="The ending commit hash.")
    args = parser.parse_args()

    print(args.start_commit)
    print(args.end_commit)