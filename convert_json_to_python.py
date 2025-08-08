import json

# Input and output filenames
input_file = "ghdb_full.json"
output_file = "embedded_ghdb.py"

def main():
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# Auto-generated file. Do not edit manually.\n")
            f.write("GHDB_DATA = ")
            json.dump(data, f, indent=4, ensure_ascii=False)

        print(f"✅ Successfully wrote embedded data to {output_file}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
