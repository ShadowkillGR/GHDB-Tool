import os
import json

def build_ghdb_json(dorks_folder, output_file="ghdb_full.json"):
    ghdb = {}

    for filename in os.listdir(dorks_folder):
        if not filename.endswith(".dorks"):
            continue

        category = filename.replace(".dorks", "").replace("_", " ").title()
        filepath = os.path.join(dorks_folder, filename)

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            dorks = [line.strip() for line in f if line.strip()]
            if dorks:
                ghdb[category] = dorks

    with open(output_file, "w", encoding="utf-8") as out:
        json.dump(ghdb, out, indent=2, ensure_ascii=False)

    print(f"[+] Generated {output_file} with {len(ghdb)} categories.")

# === USAGE ===
# Place all your *.dorks files in a folder, e.g., "dorks/"
# Then run this script:
if __name__ == "__main__":
    build_ghdb_json("dorks")  # Replace "dorks" with your folder name
