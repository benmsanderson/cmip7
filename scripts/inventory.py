"""Show what CMIP7 tas data the REF holds, and what it has processed.

For each model and experiment family, prints the number of ingested ensemble
members next to the number with a global-mean series.

    uv run scripts/inventory.py
"""

import pandas as pd

from cmip7ref import RefClient, fetch_global_mean
from cmip7ref.experiments import family


def main() -> None:
    with RefClient() as client:
        about = client.about()
        print(f"REF {about['ref_version']} (API {about['app_version']}), updated {about['last_updated']}\n")

        ds = pd.DataFrame([d["metadata"] for d in client.datasets("cmip7", variable_id="tas")])
        gm = fetch_global_mean(client)

    ingested = ds.groupby(["source_id", "experiment_id"])["variant_label"].nunique().rename("ingested")
    processed = gm.groupby(["source_id", "experiment_id"])["variant_label"].nunique().rename("gm_series")
    table = pd.concat([ingested, processed], axis=1).fillna(0).astype(int).reset_index()
    table["family"] = table["experiment_id"].map(family)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
