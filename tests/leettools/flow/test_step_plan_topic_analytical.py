from typing import Any

import pytest

from leettools.common import exceptions
from leettools.common.temp_setup import TempSetup
from leettools.common.utils.lang_utils import get_language
from leettools.context_manager import Context
from leettools.core.consts.flow_option import (
    FLOW_OPTION_NUM_OF_SECTIONS,
    FLOW_OPTION_OUTPUT_LANGUAGE,
    FLOW_OPTION_SEARCH_LANGUAGE,
)
from leettools.core.schemas.knowledgebase import KnowledgeBase
from leettools.core.schemas.organization import Org
from leettools.core.schemas.user import User
from leettools.flow import steps
from leettools.flow.schemas.article import TopicList
from leettools.flow.steps.step_plan_topic import _parse_topic_list


def test_get_research_topic_list_from_query():
    """
    TODO: we should add these kind of tests for every prompt.
    """

    temp_setup = TempSetup()

    context = temp_setup.context

    org, kb, user = temp_setup.create_tmp_org_kb_user()

    user = temp_setup.create_tmp_user()

    try:
        _test_flow_step(context, org, kb, user)
    finally:
        temp_setup.clear_tmp_org_kb_user(org, kb)


def _test_flow_step(context: Context, org: Org, kb: KnowledgeBase, user: User):

    query = "web site design"
    content = """
Designing a website involves several steps, including planning, designing, developing, testing, and launching. Here's a general guide to help you get started:

### 1. Planning
- **Purpose and Goals**: Define the purpose of the website. Is it for a business, a personal blog, an e-commerce site, etc.? Establish clear goals for what you want to achieve.
- **Target Audience**: Identify your target audience. Knowing who will visit your site helps tailor the design and content to meet their needs.
- **Content**: Plan the content you need. This includes text, images, videos, and any other media. Create a content strategy that aligns with your goals.

### 2. Designing
- **Wireframes and Mockups**: Create wireframes to outline the structure of your website. Use tools like Sketch, Figma, or Adobe XD to design mockups.
- **Branding**: Establish a visual style that includes colors, fonts, and imagery that align with your brand.
- **User Experience (UX)**: Focus on creating an intuitive and enjoyable experience for your users. Consider navigation, layout, and how users will interact with your site.
- **Responsive Design**: Ensure your design works well on various devices, including desktops, tablets, and mobile phones.

### 3. Development
- **Choose a Platform**: Decide whether to use a website builder (like WordPress, Wix, or Squarespace) or build from scratch using HTML, CSS, JavaScript, and a backend language (like Python, Ruby, or PHP).
- **Front-End Development**: Convert your designs into HTML, CSS, and JavaScript. Use frameworks like React, Vue, or Angular if needed.
- **Back-End Development**: Set up your server, database, and any necessary server-side logic. Use frameworks like Django, Flask, Ruby on Rails, or Express.js.
- **Content Management System (CMS)**: If you need to manage content easily, consider using or building a CMS.
    """

    from leettools.chat import chat_utils

    exec_info = chat_utils.setup_exec_info(
        context=context,
        query=query,
        org_name=org.name,
        kb_name=kb.name,
        username=user.username,
        flow_options={
            FLOW_OPTION_OUTPUT_LANGUAGE: "CN",
            FLOW_OPTION_SEARCH_LANGUAGE: "EN",
            FLOW_OPTION_NUM_OF_SECTIONS: 2,
        },
    )

    topic_list = steps.StepPlanTopic.run_step(exec_info=exec_info, content=content)

    assert len(topic_list.topics) == 2
    for topic in topic_list.topics:
        assert get_language(topic.title) == "zh"
        assert get_language(topic.prompt) == "en"


def test_parse_topic_list_valid_list() -> None:
    """Test parsing a valid list of topics.

    Tests that a list of topic dictionaries is correctly parsed into a TopicList object.
    """
    test_str = """[
        {
            "title": "Test Topic 1",
            "prompt": "Test prompt 1"
        },
        {
            "title": "Test Topic 2", 
            "prompt": "Test prompt 2"
        }
    ]"""

    result = _parse_topic_list(test_str)
    assert isinstance(result, TopicList)
    assert len(result.topics) == 2
    assert result.topics[0].title == "Test Topic 1"
    assert result.topics[0].prompt == "Test prompt 1"


def test_parse_topic_list_with_json_tags() -> None:
    """Test parsing a string with ```json tags.

    Tests that json code block markers are properly stripped before parsing.
    """
    test_str = """```json
    [
        {
            "title": "Test Topic",
            "prompt": "Test prompt"
        }
    ]
    ```"""

    result = _parse_topic_list(test_str)
    assert isinstance(result, TopicList)
    assert len(result.topics) == 1


def test_parse_topic_list_dict_format() -> None:
    """Test parsing a dictionary with topics key.

    Tests that a dictionary with a 'topics' key containing the topic list is parsed correctly.
    """
    test_str = """{
        "topics": [
            {
                "title": "Test Topic",
                "prompt": "Test prompt"
            }
        ]
    }"""

    result = _parse_topic_list(test_str)
    assert isinstance(result, TopicList)
    assert len(result.topics) == 1


def test_parse_topic_list_invalid_format() -> None:
    """Test parsing an invalid format raises appropriate exception.

    Tests that invalid JSON formats raise LLMInferenceResultException.
    """
    test_str = "Not a JSON string"

    with pytest.raises(exceptions.LLMInferenceResultException):
        _parse_topic_list(test_str)


def test_parse_topic_list_missing_fields() -> None:
    """Test parsing topics with missing required fields raises exception.

    Tests that topic dictionaries missing title or prompt fields raise appropriate errors.
    """
    test_str = """[
        {
            "title": "Only Title"
        }
    ]"""

    with pytest.raises(exceptions.LLMInferenceResultException):
        _parse_topic_list(test_str)
