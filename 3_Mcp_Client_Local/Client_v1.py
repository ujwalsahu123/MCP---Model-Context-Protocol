import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient  # So that we can connect our mcp client to multiple servers at the same time and use their tools/resources/prompts in a single conversation with the llm.
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import ToolMessage
import json

load_dotenv()

# need to give the Config Information of the Servers to which we want to connect our MCP client to. (we can connect to as many servers as we want, just need to give the config info of those servers here in this dict.)

SERVERS = { 

    # Local MCP Server ------------------
    "math": {
        "transport": "stdio", # the communication protocol
        
        # give command and args to start the server process 

        # Command may give -> uv 
        # args may give -> run fastmcp run main.py
        # so it becomes -> uv run fastmcp run main.py

        "command": "/Library/Frameworks/Python.framework/Versions/3.11/bin/uv", # path of uv
        "args": [
            "run",
            "fastmcp",
            "run",
            "/Users/nitish/Desktop/mcp-math-server/main.py"
       ]
    },

    # Remote MCP Server  -----------------
    "expense": {
        "transport": "streamable_http",  # if this fails, try "sse"
        "url": "https://splendid-gold-dingo.fastmcp.app/mcp"
    },

    # Local MCP Server --------------------
    "manim-server": {
        "transport": "stdio",
        "command": "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
        "args": [
        "/Users/nitish/desktop/manim-mcp-server/src/manim_server.py"
      ],
        "env": {
        "MANIM_EXECUTABLE": "/Library/Frameworks/Python.framework/Versions/3.11/bin/manim"
      }
    }
}

async def main():
    
    client = MultiServerMCPClient(SERVERS)  # make Client 
    tools = await client.get_tools() # get all the tools from all the servers that we have connected to. (it will also get the metadata of those tools like their name, description, args they take, etc.)



    # store the name of the tools & print it
    named_tools = {} 
    for tool in tools:
        named_tools[tool.name] = tool

    print("Available tools:", named_tools.keys())



    # import model and bind tools to it so that when the llm is used then the tools info will also be send to the llm and then the llm can decide which tool to use for which prompt.
    llm = ChatOpenAI(model="gpt-5")
    llm_with_tools = llm.bind_tools(tools)



    ##################################################      
    # write prompt and get response from the model. 
    # (the model will check which tool to use for this prompt, but it directly dosent have the power to call the tool itself, so it will give an output 
    # where it will tell that use this tool and give this argument in it. 
    # ex :- LLM response -> tool calls = [{"name": "manim-server-tool", "args": {"scene_description": "a triangle rotating in place"}, "id": "1234"}]   , it will give this alag say and not in response.content part.
    # and then we have to call the tool by ourself and give it the argument that the llm has told us to give and then get the response from the tool and then give that response back to the llm so that it can give us the final output.
     


    # prompt the llm and get response having the tool call info in it.
    prompt = "Draw a triangle rotating in place using the manim tool."
    response = await llm_with_tools.ainvoke(prompt)


    # if there is no tool call info in the response then it means the llm dosent want to use any tool for this prompt and it can give the final response directly in the response.content part. so we can check if there is tool call info in the response or not and if not then we can directly print the response.content as the final output.
    if not getattr(response, "tool_calls", None):
        print("\nLLM Reply:", response.content)
        return # no need to do anything else as there is no tool call needed.



    # Now to call the tool first we extract the tool name , agrs , id from the response .
    tool_messages = []
    for tc in response.tool_calls:
        selected_tool = tc["name"]
        selected_tool_args = tc.get("args") or {}
        selected_tool_id = tc["id"]

        # and then for each tool we call the tool by ourself . 
        # ex:- tool_name.ainvoke(args) 
        # loop may hai so it will do it for multiple tools if the llm has given multiple tool calls in the response.
        result = await named_tools[selected_tool].ainvoke(selected_tool_args)
        # and store all the info (tool_name, arg , id , result) in a list of tool messages so that we can give it back to the llm after calling the tool and then the llm can give us the final response by using that info.
        tool_messages.append(ToolMessage(tool_call_id=selected_tool_id, content=json.dumps(result)))  # using the ToolMessage to store the tool call info and the result of the tool call in a structured way so that we can give it back to the llm.
        


    # Now we give the response of the tool calls back to the llm and ask it to give us the final response by using that tool response info.
    final_response = await llm_with_tools.ainvoke([prompt, response, *tool_messages])
    print(f"Final response: {final_response.content}")


if __name__ == '__main__':
    asyncio.run(main())