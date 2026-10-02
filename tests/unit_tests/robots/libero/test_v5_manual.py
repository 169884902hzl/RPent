from pathlib import Path

from robots.libero.v5_manual import GENERAL_RULES, manual_text


def test_general_manual_does_not_read_the_task_or_rpent_files(tmp_path):
    text,files=manual_text('general',tmp_path)
    assert text==GENERAL_RULES and files==[]
    assert 'libero' not in text.lower() and 'task 0' not in text.lower()
    assert manual_text('none',tmp_path)==(None,[])


def test_rpent_manual_keeps_original_guide_bytes_and_no_memory_configuration():
    root=Path(__file__).resolve().parents[4]
    text,files=manual_text('rpent',root)
    assert 'MEMORY PROFILE — EMPTY' in text
    assert all(p.read_text() in text for p in files[1:])
