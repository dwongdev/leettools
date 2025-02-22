from leettools.common.utils.lang_utils import get_language


def test_lang_utils():
    # Test case 1: en
    content = "This is an image: ![alt text](https://example"
    lan = get_language(content)
    assert lan == "en"

    # Test case 2: zh
    content = "这是一张图片: ![alt text](https://example"
    lan = get_language(content)
    assert lan == "zh" or lan == "en"

    # Test case 3: ja
    content = "これは画像です: ![alt text](https://example"
    lan = get_language(content)
    assert lan == "ja"

    # Test case 5: spanish
    content = "Hoy es un día maravilloso"
    lan = get_language(content)
    assert lan == "es"

    # Test case 6: french
    content = "C'est une belle journée"
    lan = get_language(content)
    assert lan == "fr"

    # Test case 7: mixed
    content = "This is an image: ![alt text](https://example 这是一张图片"
    lan = get_language(content)
    assert lan == "en"

    # Test case 8: empty
    content = ""
    lan = get_language(content)
    assert lan == "en"
