import os

from dotenv import load_dotenv

from kobo import KoboClient

load_dotenv()

def main() -> None:
    token = os.environ["KEY"]
    client = KoboClient(api_token=token)

    # 1. List available surveys
    print("=== Surveys ===")
    surveys = client.get_surveys()
    for s in surveys:
        print(f"  [{s['uid']}] {s['name']}  (status: {s.get('deployment_status', 'draft')})")

    if not surveys:
        print("No surveys found.")
        return

    # Work with the first survey
    uid = surveys[0]["uid"]
    print(f"\nUsing survey: {uid}")

    # 2. Survey structure (XLSForm content)
    print("\n=== Survey content (first 5 questions) ===")
    content = client.get_survey_content(uid)
    for row in content.get("survey", [])[:5]:
        print(f"  {row.get('type', ''): <20} {row.get('$autoname', row.get('name', ''))}")

    # 3. Export rápido: configuración + trigger + descarga en un solo método
    print("\n=== Descargando Excel ===")
    saved = client.get_excel(uid, path="data_survey.xlsx")
    print(f"  Guardado en: {saved}")


if __name__ == "__main__":
    main()
