from ml_ui.config import LOGS_DIR
import logging
from datetime import datetime
from nicegui import ui
import requests
import ast

logger = logging.getLogger(__name__)


def setup_logging():
    log_file_path = LOGS_DIR / f"{datetime.today().date()}.log"

    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)


def main():
    logger.info("Starting ML UI")

    ui.label("ML Prediction UI")

    with ui.row():
        input_box = ui.textarea(label="Input [1, 2, 3]").props(
            'autogrow style="width:400px; max-height:200px; overflow:auto"'
        )
        output_box = ui.textarea(label="Output").props(
            "readonly autogrow style="
            '"width:400px; max-height:200px; overflow:auto"'
        )

    def predict():
        logger.info("Predict button pressed")
        try:
            data = ast.literal_eval(input_box.value)
            if not isinstance(data, list) or not all(
                isinstance(x, (int, float)) for x in data
            ):
                raise ValueError("Expected list of numbers")
            response = requests.post(
                "http://localhost:8000/predict", json={"data": data}
            )
            result = response.json()
            output_box.value = (
                f"Prediction: {result.get('predictions', result)}"
            )
            logger.info(f"Prediction success: {result}")
        except Exception as e:
            output_box.text = f"Error: {e}"
            logger.warning(f"Prediction failed: {e}")

    ui.button("Predict", on_click=predict)

    ui.run(port=8080, reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    setup_logging()
    main()
