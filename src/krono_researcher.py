# src/krono_researcher.py

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import Literal
from langgraph.graph.state import RunnableConfig
from langgraph.types import Command

from src.configuration import Configuration
from src.prompts import lead_researcher_prompt
from src.utils import get_api_key_for_model, think_tool
from src.state import (
    ConductResearch,
    ResearchComplete,
    SupervisorState,
    SupervisorStateInput,
)

load_dotenv()


# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)


async def supervisor(
    state: SupervisorState, config: RunnableConfig
) -> Command[Literal["supervisor_tools"]]:
    # Step 1: Configure the supervisor model with available tools
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"],
    }
    person_researcher_tools = [ConductResearch, ResearchComplete, think_tool]
    person_to_research = state.get("person_to_research", "")

    if not person_to_research:
        raise ValueError("Person to research is required")

    research_model = (
        configurable_model.bind_tools(person_researcher_tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )

    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    if research_iterations == 0:
        print("first iteration")
        supervisor_messages = [
            SystemMessage(content=lead_researcher_prompt),
            HumanMessage(content=person_to_research),
        ]

    # Step 2: Invoke the supervisor model with the search messages
    response = await research_model.ainvoke(supervisor_messages)

    if research_iterations == 0:
        messages_to_add = supervisor_messages + [response]
    else:
        # On subsequent runs, just add the latest AI response.
        messages_to_add = [response]

    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": messages_to_add,
            "research_iterations": state.get("research_iterations", 0) + 1,
        },
    )


async def supervisor_tools(
    state: SupervisorState, config: RunnableConfig
) -> Command[Literal["supervisor", END]]:
    """Execute tools called by the supervisor, including research delegation and strategic thinking.

    This function handles three types of supervisor tool calls:
    1. think_tool - Strategic reflection that continues the conversation
    2. ConductResearch - Delegates research tasks to sub-researchers
    3. ResearchComplete - Signals completion of research phase

    Args:
        state: Current supervisor state with messages and iteration count
        config: Runtime configuration with research limits and model settings

    Returns:
        Command to either continue supervision loop or end research phase
    """
    # Step 1: Extract current state and check exit conditions
    configurable = Configuration.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]

    # Define exit criteria for research phase
    exceeded_allowed_iterations = (
        research_iterations > configurable.max_researcher_iterations
    )
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in most_recent_message.tool_calls
    )

    # Exit if any termination condition is met
    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(goto=END)

    # Step 2: Process all tool calls together (both think_tool and ConductResearch)
    all_tool_messages = []
    update_payload = {"supervisor_messages": []}

    # Handle think_tool calls (strategic reflection)
    think_tool_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "think_tool"
    ]

    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection"]
        all_tool_messages.append(
            ToolMessage(
                content=f"Reflection recorded: {reflection_content}",
                name="think_tool",
                tool_call_id=tool_call["id"],
            )
        )

    # Handle ConductResearch calls (research delegation)
    conduct_research_calls = [
        tool_call
        for tool_call in most_recent_message.tool_calls
        if tool_call["name"] == "ConductResearch"
    ]

    if conduct_research_calls:
        raise ValueError("ConductResearch calls are not supported yet")
    #     for tool_call in conduct_research_calls:
    #         research_person = tool_call["args"]["research_person"]
    #         all_tool_messages.append(ToolMessage(
    #             content=f"Researching {research_person}",
    #             name="ConductResearch",
    #             tool_call_id=tool_call["id"]
    #         ))
    #         update_payload["supervisor_messages"].append(ToolMessage(
    #             content=f"Researching {research_person}",
    #             name="ConductResearch",
    #             tool_call_id=tool_call["id"]
    #         ))

    # Step 3: Return command with all tool results
    update_payload["supervisor_messages"] = all_tool_messages
    return Command(goto="supervisor", update=update_payload)


# Build the graph
graph_builder = StateGraph(SupervisorState, input_schema=SupervisorStateInput)

graph_builder.add_node("supervisor", supervisor)
graph_builder.add_node("supervisor_tools", supervisor_tools)

graph_builder.add_edge(START, "supervisor")

graph = graph_builder.compile()
