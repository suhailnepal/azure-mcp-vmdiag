from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate
from langchain.chains import ConversationChain

llm = ChatOllama(
    model="llama3.1:8b",
    temperature=0,
    # other params...
)

memory = ConversationBufferMemory()

template = """The following is a friendly conversation between a human and an AI.
The AI is talkative and provides lots of specific details from its context.

Current conversation:
{history}
Human: {input}
AI:"""

prompt = PromptTemplate(input_variables=["history", "input"], template=template)


# 4. Create the ConversationChain Instance
# Pass the LLM, the memory, and the prompt template
conversation = ConversationChain(
    llm=llm,
    memory=memory,
    prompt=prompt,
    verbose=True  # Set to True to see the internal workings (prompts sent to LLM)
)

# 5. Interact with the Chatbot
print("Chatbot initialized. Type 'exit' to end the conversation.")

while True:
    user_input = input("You: ")
    if user_input.lower() == 'exit':
        print("Exiting chat. Goodbye!")
        break

    try:
        # Use .invoke() to get the response from the chain
        # The chain automatically manages passing history and new input to the LLM
        response = conversation.invoke({"input": user_input})
        print(f"AI: {response['response']}") # The output key is 'response' by default for ConversationChain
    except Exception as e:
        print(f"An error occurred: {e}")
        print("Please ensure Ollama is running and the 'llama3' model is available.")
