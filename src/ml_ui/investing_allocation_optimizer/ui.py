import logging
from nicegui import ui
import requests
import ast
from ml_ui.utils import setup_logging


def main():
    logger = logging.getLogger(__name__)

    logger.info("Starting ML UI")

    ui.label("ML Prediction UI")

    with ui.row():
        input_box = ui.textarea(
            label="Input",
            value="""{
        "data": {
            "metric": "mean",
            "p_1_constraint": 0,
            "p_5_constraint": 0,
            "max_std": 0,
            "n_trials": 100,
            "random_seed": 0,
            "bootstrap_block_size": "cube root",
            "bootstrap_path_length": 100,
            "n_bootstrap_paths": 1000
        }
    }""",
        ).props(
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
            if not isinstance(data, dict):
                raise ValueError("Expected dict.")
            response = requests.post(
                "http://serving:8000/predict", json={"data": data}
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
