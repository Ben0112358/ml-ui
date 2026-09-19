import json
import logging

import requests
import streamlit as st

from ml_ui.utils import setup_logging


def main() -> None:
    logger = logging.getLogger(__name__)
    setup_logging()
    st.title("ML Prediction UI (dummy)")
    raw = st.text_area("Input list", value="[1, 2, 3]")
    if st.button("Predict"):
        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError("Input must be a JSON list.")
            response = requests.post(
                "http://serving:8000/predict",
                json={"data": data},
                timeout=30,
            )
            st.json(response.json())
            logger.info("Prediction success")
        except Exception as exc:
            st.error(str(exc))


if __name__ == "__main__":
    main()
