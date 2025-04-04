import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from pydantic import BaseModel
from ragas.dataset_schema import EvaluationResult

from leettools.chat import chat_utils
from leettools.chat.history_manager import get_history_manager
from leettools.cli.cli_utils import setup_org_kb_user
from leettools.common.logging import logger
from leettools.common.utils import time_utils
from leettools.context_manager import Context, ContextManager
from leettools.core.consts import flow_option
from leettools.core.consts.docsource_type import DocSourceType
from leettools.core.consts.retriever_type import RetrieverType
from leettools.core.schemas.docsource import DocSourceCreate
from leettools.flow.exec_info import ExecInfo
from leettools.flow.utils import pipeline_utils

"""
Evaluate the pipeline give a test directory that contains:
- the source documents
- the sample questions, the expected answers, the expected sources

The pipeline will:
- ingest the source documents into a knowledge base based on a given settings
- run the sample questions against the knowledge base
- generate the final evaluation dataset and feed it in RAGAS
"""


class AnswerSource(BaseModel):
    # we may add location information in the future
    source_text: str


class EvalDataItem(BaseModel):
    question: str
    expected_answer: str
    expected_sources: List[AnswerSource] = []


class EvalDataSet(BaseModel):
    input_files: List[str]
    sample_data: List[EvalDataItem]


sample_docs = [
    "Albert Einstein proposed the theory of relativity, which transformed our understanding of time, space, and gravity.",
    "Marie Curie was a physicist and chemist who conducted pioneering research on radioactivity and won two Nobel Prizes.",
    "Isaac Newton formulated the laws of motion and universal gravitation, laying the foundation for classical mechanics.",
    "Charles Darwin introduced the theory of evolution by natural selection in his book 'On the Origin of Species'.",
    "Ada Lovelace is regarded as the first computer programmer for her work on Charles Babbage's early mechanical computer, the Analytical Engine.",
]

sample_queries = [
    "Who introduced the theory of relativity?",
    "Who was the first computer programmer?",
    "What did Isaac Newton contribute to science?",
    "Who won two Nobel Prizes for research on radioactivity?",
    "What is the theory of evolution by natural selection?",
]

expected_responses = [
    "Albert Einstein proposed the theory of relativity, which transformed our understanding of time, space, and gravity.",
    "Ada Lovelace is regarded as the first computer programmer for her work on Charles Babbage's early mechanical computer, the Analytical Engine.",
    "Isaac Newton formulated the laws of motion and universal gravitation, laying the foundation for classical mechanics.",
    "Marie Curie was a physicist and chemist who conducted pioneering research on radioactivity and won two Nobel Prizes.",
    "Charles Darwin introduced the theory of evolution by natural selection in his book 'On the Origin of Species'.",
]


def create_example_eval_file() -> EvalDataSet:

    # Create a persistent temporary directory
    tmp_dir = tempfile.mkdtemp()
    # Convert it to a pathlib.Path object
    tmp_path = Path(tmp_dir)
    logger().debug(f"Temporary directory created: {tmp_path}")

    file_id: int = 1
    file_paths: List[Path] = []
    for doc in sample_docs:
        file_path = tmp_path / f"doc_{file_id}.txt"
        file_path.write_text(doc)
        file_id += 1
        file_paths.append(file_path)

    sample_data: List[EvalDataItem] = []
    for query, expected_response in zip(sample_queries, expected_responses):
        eval_data_item = EvalDataItem(
            question=query,
            expected_answer=expected_response,
            expected_sources=[AnswerSource(source_text=expected_response)],
        )
        sample_data.append(eval_data_item)

    eval_data = EvalDataSet(
        input_files=[str(file_path) for file_path in file_paths],
        sample_data=sample_data,
    )
    return eval_data


from eval.utils.standalone_pipeline import standalone_converter
from eval.utils.utils import setup_context, setup_exec_info


def run_converter(raw_doc_path: str, kb_name: str):
    """Convert documents without chunking or embedding."""

    context = setup_context(kb_name)

    org, kb, user = setup_org_kb_user(context, None, kb_name, None)

    standalone_converter(raw_doc_path, context, org, kb)


# def run_converter(eval_data: EvalDataSet) -> ExecInfo:
#     """Convert documents without chunking or embedding."""
#     timestamp = time_utils.cur_timestamp_in_ms()
#     kb_name = f"eval_{timestamp}"

#     context = ContextManager().get_context()  # type: Context
#     context.is_svc = False
#     context.name = f"{context.EDS_CLI_CONTEXT_PREFIX}_eval"

#     repo_manager = context.get_repo_manager()
#     docsource_store = repo_manager.get_docsource_store()

#     display_logger = logger()

#     org, kb, user = setup_org_kb_user(context, None, kb_name, None)
#     org_name = org.name
#     username = user.username

#     for file in eval_data.input_files:
#         # Verify file exists before processing
#         if not Path(file).exists():
#             display_logger.error(f"File does not exist: {file}")
#             continue
            
#         docsource_create = DocSourceCreate(
#             org_id=org.org_id,
#             kb_id=kb.kb_id,
#             source_type=DocSourceType.LOCAL,
#             uri=file,
#         )
#         docsource = docsource_store.create_docsource(org, kb, docsource_create)
#         pipeline_utils.process_docsource_manual(
#             org=org,
#             kb=kb,
#             user=user,
#             docsource=docsource,
#             context=context,
#             display_logger=display_logger,
#             convert_only=True,  # Always convert only
#         )
    
#     exec_info = chat_utils.setup_exec_info(
#         context=context,
#         query="dummy",
#         org_name=org.name,
#         kb_name=kb_name,
#         username=username,
#         strategy_name=None,
#         flow_options={
#             flow_option.FLOW_OPTION_RETRIEVER_TYPE: RetrieverType.LOCAL,
#         },
#         display_logger=None,
#     )
#     return exec_info, org, kb, user


from eval.utils.standalone_pipeline import standalone_splitter_embedder


def run_chunker_embedder(exec_info: ExecInfo, org, kb, user):
    """Run chunking and embedding on already converted documents."""
    standalone_splitter_embedder(org, kb, exec_info, user)


def run_ingestion(raw_doc_path: str, kb_name: str):
    """Run the complete ingestion process with option to only convert."""
    # exec_info, org, kb, user = run_converter(eval_data)
    
    # if not convert_only:
    #     exec_info = run_chunking_embedding(eval_data, exec_info, org, kb, user)
    
    # return exec_info
    pass


def run_queries(eval_data: EvalDataSet, exec_info: ExecInfo) -> List[Dict[str, Any]]:

    context = exec_info.context
    chat_manager = get_history_manager(context)
    dataset: List[Dict[str, Any]] = []

    for eval_data_item in eval_data.sample_data:

        query = eval_data_item.question
        reference = eval_data_item.expected_answer

        exec_info.query = query
        exec_info.target_chat_query_item.query_content = query

        chat_query_result = chat_manager.run_query_with_strategy(
            org=exec_info.org,
            kb=exec_info.kb,
            user=exec_info.user,
            chat_query_item_create=exec_info.target_chat_query_item,
            chat_query_options=exec_info.chat_query_options,
            strategy=exec_info.strategy,
        )

        relevant_docs = []
        cai = chat_query_result.chat_answer_item_list[0]
        response = cai.answer_content
        for citation in cai.answer_source_items.values():
            relevant_docs.append(citation.answer_source.source_content)

        dataset.append(
            {
                "user_input": query,
                "retrieved_contexts": relevant_docs,
                "response": response,
                "reference": reference,
            }
        )
    return dataset


def run_eval(dataset: List[Dict[str, Any]]) -> EvaluationResult:
    from ragas import EvaluationDataset

    evaluation_dataset = EvaluationDataset.from_list(dataset)

    from langchain_openai import ChatOpenAI
    from ragas import evaluate
    from ragas.llms import LangchainLLMWrapper

    llm = ChatOpenAI(model="gpt-4o-mini")
    evaluator_llm = LangchainLLMWrapper(llm)
    from ragas.metrics import (FactualCorrectness, Faithfulness,
                               LLMContextRecall)

    result = evaluate(
        dataset=evaluation_dataset,
        metrics=[LLMContextRecall(), Faithfulness(), FactualCorrectness()],
        llm=evaluator_llm,
    )
    return result


@click.command(help="Evaluate the pipeline with the input data.")
@click.option(
    "-c",
    "--create-example",
    "create_example",
    is_flag=True,
    required=False,
    help="Create an example of the eval file.",
)
@click.option(
    "-i",
    "--ingestion-pipeline-operation",
    "ingestion_pipeline_operation",
    type=click.Choice(["full", "convert", "embed"]),
    default=None,
    required=False,
    help="Ingestion pipeline operation: \n'full' runs complete pipeline, \n'convert' only converts documents, \n'embed' continues utilizing chunker and embedder after converter.",
)
@click.option(
    "-e",
    "--evaluation",
    "evaluation",
    is_flag=True,
    required=False,
    help="Run evaluation on the dataset after ingestion.",
)


def eval_orchestrator(create_example: Optional[bool] = False, 
         ingestion_pipeline_operation: Optional[str] = None, 
         evaluation: Optional[bool] = False, 
         eval_file: str = "eval/eval.conf.json"):

    if create_example:
        eval_data = create_example_eval_file()
        print(eval_data.model_dump_json(indent=2))
        return

    # expand the eval_file to the full path
    eval_file_path = Path(eval_file).absolute()
    with open(eval_file_path, "r", encoding="utf-8") as f:
        eval_data = EvalDataSet.model_validate_json(f.read())
    
    display_logger = logger()

    display_logger.info(f"Loaded eval data from {eval_file_path}")
    raw_doc_path = Path(eval_data.input_files[0]).parent
    kb_name = raw_doc_path.stem

    if ingestion_pipeline_operation:
        if ingestion_pipeline_operation == "convert":
            display_logger.info("Manually run converter only...")
            run_converter(raw_doc_path, kb_name)
        elif ingestion_pipeline_operation == "embed":
            display_logger.info("Manually run chunker and embedder...")
            exec_info, org, kb, user = setup_exec_info(
                kb_name=kb_name, logger=display_logger, return_org_kb_user=True)
            run_chunker_embedder(exec_info, org, kb, user)
        else:
            # full ingestion pipeline
            run_ingestion(raw_doc_path, kb_name)
                # Pass the convert_only parameter to run_ingestion
                # exec_info = run_ingestion(eval_data)
                # logger().info("Ingestion completed.")

    if evaluation: # all zeros if embeeding hasn't been run
        exec_info = setup_exec_info(
            kb_name=kb_name, logger=display_logger)
        display_logger.info("Running queries...")
        dataset = run_queries(eval_data, exec_info)
        display_logger.info("Queries completed.")

        display_logger.info("Running evaluation...")
        result = run_eval(dataset)
        display_logger.info("Evaluation completed.")

        print(result)


if __name__ == "__main__":
    eval_orchestrator()
