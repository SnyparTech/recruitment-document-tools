from unittest.mock import MagicMock
import pytest
from selenium.webdriver.common.by import By
from app.selenium.form_executor import ResdexFormExecutor


@pytest.fixture
def mock_driver_and_executor():
    driver = MagicMock()
    wait = MagicMock()
    executor = ResdexFormExecutor(driver=driver, wait=wait)
    return driver, wait, executor


def test_executor_fill_text(mock_driver_and_executor):
    driver, wait, executor = mock_driver_and_executor
    mock_el = MagicMock()
    wait.until.return_value = mock_el

    success = executor.fill_text(selector="#keywords", value="Python FastAPI")

    assert success is True
    mock_el.clear.assert_called_once()
    mock_el.send_keys.assert_called_once_with("Python FastAPI")


def test_executor_fill_number(mock_driver_and_executor):
    driver, wait, executor = mock_driver_and_executor
    mock_el = MagicMock()
    wait.until.return_value = mock_el

    success = executor.fill_number(selector="#minExp", value=3.0)

    assert success is True
    mock_el.send_keys.assert_called_once_with("3")


def test_executor_fill_checkbox(mock_driver_and_executor):
    driver, wait, executor = mock_driver_and_executor
    mock_el = MagicMock()
    mock_el.is_selected.return_value = False
    wait.until.return_value = mock_el

    success = executor.fill_checkbox(selector="#relocate", checked=True)

    assert success is True
    mock_el.click.assert_called_once()


def test_executor_fill_range(mock_driver_and_executor):
    driver, wait, executor = mock_driver_and_executor
    mock_el = MagicMock()
    wait.until.return_value = mock_el

    success = executor.fill_range(
        min_selector="#minExp",
        max_selector="#maxExp",
        min_val=2.0,
        max_val=5.0,
    )

    assert success is True
    assert mock_el.send_keys.call_count == 2


def test_executor_submit_form(mock_driver_and_executor):
    driver, wait, executor = mock_driver_and_executor
    mock_btn = MagicMock()
    wait.until.return_value = mock_btn

    success = executor.submit_form(button_selector="#searchBtn")

    assert success is True
    mock_btn.click.assert_called_once()
