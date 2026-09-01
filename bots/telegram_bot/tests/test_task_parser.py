from datetime import datetime

from services.tasks.parser import TaskParser


def test_parse_relative_minutes():
    result = TaskParser.parse(
        "یادم بنداز 30 دقیقه دیگه به یونس زنگ بزن"
    )

    assert result["title"] == "به یونس زنگ بزن"
    assert result["due_date"]
    assert result["due_time"]


def test_parse_relative_hours():
    result = TaskParser.parse(
        "یادم بنداز 2 ساعت دیگه جلسه داشته باشم"
    )

    assert result["title"] == "جلسه داشته باشم"
    assert result["due_date"]
    assert result["due_time"]


def test_parse_tomorrow_with_time():
    result = TaskParser.parse(
        "یادم بنداز فردا ساعت 8 جلسه"
    )

    assert result["title"] == "جلسه"
    assert result["due_date"]
    assert result["due_time"] == "08:00"


def test_parse_tomorrow_with_minute():
    result = TaskParser.parse(
        "یادم بنداز فردا ساعت 8:30 جلسه"
    )

    assert result["title"] == "جلسه"
    assert result["due_date"]
    assert result["due_time"] == "08:30"


def test_parse_persian_digits():
    result = TaskParser.parse(
        "یادم بنداز ۳۰ دقیقه دیگه دارو بخر"
    )

    assert result["title"] == "دارو بخر"
    assert result["due_date"]
    assert result["due_time"]


def test_parse_arabic_digits():
    result = TaskParser.parse(
        "یادم بنداز ٣٠ دقیقه دیگه خرید کنم"
    )

    assert result["title"] == "خرید کنم"
    assert result["due_date"]
    assert result["due_time"]


def test_parse_today():
    result = TaskParser.parse(
        "یادم بنداز امروز ساعت 18 ورزش کنم"
    )

    assert result["title"] == "ورزش کنم"
    assert result["due_date"]
    assert result["due_time"] == "18:00"


def test_parse_day_after_tomorrow():
    result = TaskParser.parse(
        "یادم بنداز پس فردا ساعت 10 جلسه"
    )

    assert result["title"] == "جلسه"
    assert result["due_date"]
    assert result["due_time"] == "10:00"


def test_parse_time_without_date():
    now = datetime.now()

    result = TaskParser.parse(
        "یادم بنداز ساعت 23:59 تست کنم"
    )

    assert result["title"] == "تست کنم"
    assert result["due_date"]
    assert result["due_time"] == "23:59"


def test_parse_task_without_due_date():
    result = TaskParser.parse(
        "یادم بنداز پروژه رو کامل کنم"
    )

    assert result["title"] == "پروژه رو کامل کنم"
    assert result["due_date"] == ""
    assert result["due_time"] == ""


def test_empty_title():
    result = TaskParser.parse(
        "یادم بنداز"
    )

    assert result["title"] == "کار بدون عنوان"


def test_invalid_time_is_not_accepted():
    result = TaskParser.parse(
        "یادم بنداز ساعت 25:90 تست کنم"
    )

    assert result["due_time"] == ""
    assert result["title"] != "تست کنم"


def test_trigger_is_removed():
    result = TaskParser.parse(
        "یادآوری کن فردا ساعت 9 تماس بگیر"
    )

    assert "یادآوری کن" not in result["title"]
    assert result["title"] == "تماس بگیر"


def test_english_trigger():
    result = TaskParser.parse(
        "remind me tomorrow"
    )

    assert "remind" not in result["title"].lower()


def test_task_title_cleanup():
    result = TaskParser.parse(
        "یادم بنداز   فردا   ساعت 8    خرید کنم"
    )

    assert result["title"] == "خرید کنم"