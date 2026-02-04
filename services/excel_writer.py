import pandas as pd
import json

def json_to_excel(json_text, filename="output.xlsx"):
    data = json.loads(json_text)
    df = pd.DataFrame(data["rows"])
    df.to_excel(filename, index=False)
    return filename
