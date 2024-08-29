This list will evolve as the bot progresses. We'll start getting features working, and add polish later.

## Current Tasks

### Today

- [ ] Implement an overall status message that can be fed into Bob

### Todo

#### Activities

- [ ] Allow Bob to comment on current activities
- [ ] Allow Bob to auto-start activities based on context

#### Memory

- [ ] Make a summarizer agent that can take in chat history and create a <= N-word summary, where N is a parameter that the user (caller) can control
- [ ] Make a memory agent that reads chat history and determines important factual memories to store. Memories can be rated by their significance (is it important to remember?), relevancy (will it come up later?) objectiveness (is it a fact?), and accuracy (is the info provably correct?) on scales of 1-10. Potentially split this up into 2 agents, one that generates the memory and one that does the ratings (a verifier).
  - Some good references to go off of: [This video demonstrating a ChatGPT-like readable long term memory system](https://www.youtube.com/watch?v=oPCKB9MUP6c), [this Github repo using hierarchical memory](https://github.com/kyb3r/emergent/blob/main/emergent/memory.py), and [the corresponding design document](https://github.com/daveshap/HierarchicalMemoryConsolidationSystem).
  - It looks like no specifically designed libraries exist for creating these memories, so let's build this up ourselves, potentially reusing other people's code, with citations.
- [ ] Use the memory agent to create candidate long-term memories. Then, before putting them in the vector store, retrieve similar memories that already exist, and combine them into a "knowledge base article" or similar.
  - We could potentially use [LlamaIndex](https://medium.com/llamaindex-blog/data-agents-eed797d7972f) to process the memories once we've created them. I'm not sure how this would fit together yet.
- [ ] Implement a memory pruning system that just prunes the oldest memories which haven't been retrieved/updated upon reaching a limit, or prunes memories that haven't been retrieved/updated for X days (maybe incremental, like spaced repetition retention times).

#### Smarts

- [ ] Implement a system that switches to deepseek (model/prompt) when very edgy or NSFW responses are needed, can be detecting using OpenAI's moderation API
- [ ] Implement a web search tool in the agents subpackage, splitting into files (modules) as needed for organization (try to avoid OOP/state)

#### Quality of Life

- [ ] Add URLs property to ParsedMessage that contains a list of all URLs present in a message (valid or not)
- [ ] Add a delayed second check on whether to send a message or not, to be ran when no one is typing and Bob decided not to respond before (due to not being sure if the other person was done). In this delayed check, emphasize to the decision agent that all users are done typing.
- [ ] Think of a way to fix sending multiple messages at once that does not involve the decision maker running again when Bob sent the last message (that doesn't work). Switching Bob's prompt to allow for multiple messages as a response doesn't work well. The best way likely involves a small LLM at the end deciding how to split up a long message into smaller messages, since this won't be influenced by history.
- [ ] Make a Discord status message based on current activity

### Future

- [ ] Optimize TextChannelHistory token usage by truncating messages
- [ ] Add medium-term memory to TextChannelHistory by summarizing long messages and those that go out of the window
- [ ] Implement simulated work, sleep, eat, and shower activities
- [ ] Implement some sort of auto schedule planner that decides when Bob will do certain activities each day (by default, but Bob can override this)
- [ ] Add tests for stable functions (that likely won't change)

## Completed Tasks

### Basics

- [x] Finally finish setting up the Python development environment
- [x] Plan out how Bob will be structured (at a high level) in V2
- [x] Attempt to use Crew.AI to build the V1 multiagent system (conclusion: Crew.AI sucks)
- [x] Attempt to use AutoGen to build something like the V1 multiagent system
- [x] Implement default and off modes, along with default and instant speeds
- [x] Reorganize by moving the bot and the agent into classes (for easier abstraction/usage) (decided not to do for now, instead put them in separate functions)
- [x] Make Bob easier to debug by allowing debug info to be printed on demand in Discord

### Text

- [x] Implement a class that abstracts away Discord text channel history/event handling
- [x] Improve TextChannelHistory to include details about replies, reactions, stickers, and attachments
- [x] Improve TextChannelHistory to include details about edited and deleted messages
- [x] Begin to optimize TextChannelHistory token usage by truncating messages based on how recent they are
- [x] (Re)implement a bare bones version of Bob by passing in message history with a simple system prompt and a single agent
- [x] Wait for users to finish typing before sending a message
- [x] Clean up message history class (OOP kinda sucks ngl)
- [x] Bring back the original Bob's chatting style, and keep it that way

### Memory

hi

### Activities

- [x] Learn how to use Playwright
- [x] Implement a basic auto-chess player using Playwright that can go to a pre-generated invite link and play a full game
- [x] Incorporate activities into Bob through direct commands
- [x] Get bob to play chess at a rating of ~800 (intentionally low) by fixing the dumb broken chess API system
- [x] Chess polishing: Send result message first and close game over prompt before taking final screenshot
- [x] Add new commands to help text
- [x] Try using GPT to help create a prompt for GPT :p
- [x] Allow Bob to relay commands to the user in an appropriate style
- [x] Allow Bob to ask and receive answers to commands in an appropriate style using an answer extraction agent

### Multi-agent

- [x] Implement a basic chain: Response decision -> Message sender
- [x] Refine message quality and handle content filtering by testing different models

## Milestones and Capstones

### Text

- [x] Have Bob send a hello world message in Discord (7/13/24)
- [x] Hold a decently intelligble conversation with someone (7/13/24)
- [x] Demonstrate flexibility by playing 20 questions (7/14/24)
- [x] Demonstrate emerging reasoning skills by identifying League champs (7/15/24)
- [x] Recognize and be able to vaguely discuss images (8/18/24)
- [ ] Demonstrate improved reasoning skills by playing Jeopardy decently
- [ ] Send multiple messages at once, or send no messages when appropriate in a non-hacky way
- [ ] Initiate a DM or group chat conversation after being inactive for a while
- [ ] Remember details about people from a long time ago, say >50 messages
- [ ] Have a persistent mood and/or life story through simulated emotions and events
- [ ] Understand the difference between DMs and servers, and participate in both of them
- [ ] **Capstone:** Hold an emotional and long (requiring memory) chat conversation in DMs while acting similar to a human
- [ ] **Capstone:** Act like a normal, active Discord user in a medium sized server, replying to or initiating messages

### Voice

- [x] Join voice chat and play some music (7/15/24)
- [x] Be able to respond intelligbly to someone talking in voice chat (7/18/24)
- [ ] Respond in a more human-like voice
- [ ] Generate a response in near real-time, quick enough to not be awkward
- [ ] Integrate text chat capabilities (memory, emotions, reasoning) into voice chat
- [ ] **Capstone:** Participate decently in a group voice chat, in real-time!

### Gaming

- [x] Play Chess at a rating > 800, for an easy-to-play (ish) proof of concept
- [ ] **Capstone:** Play League, a comprehensive, tough game with an anticheat

### All Together

- [ ] **Capstone:** Have a user ask Bob to join voice chat, then ask to play a game on Discord, then have him actually join and play that video game!

From [the initial Node.js version](https://github.com/Giantpizzahead/bob-bot-ts):

## (Old) TypeScript Era

- [x] Initial bot setup, texting, commands, etc (didn't have a todo list in the beginning)
- [x] Encourage the bot to send many more messages than 1 or 2
- [x] Emulate work and sleep times, for realism and also to avoid distractions
- [x] Try to implement reasoning skills but realize that it's kinda not very good
- [x] Implement a period update to allow Bob to initiate its own messages
- [x] Make the bot send messages unprompted after long, random delays
- [x] Implement simple TTS
- [x] Switch to openrouter api
- [x] Create a small eval suite for models
- [x] Test top roleplay rated cheap models
- [x] Switch to an uncensored model using OpenRouter
- [x] Change Bob's status when working or sleeping
- [x] Make a bare bones version of Bob (text only) for ease of testing and development
- [x] Try out Langchain with JS, see how it works
- [x] Begin looking into short and long term memory
- [x] Implement a RAG system using LangChain, embeddings, lookup queries, and a vector store
- [x] Try out LangChain tool (function) calling
- [x] Integrate an online search engine into bare bones Bob
- [x] Try other forms of conversational memory (apart from just a buffer)
- [x] Try persistent, multi-agent paradigms in LangGraph
- [x] Try persistent, multi-agent paradigms using other tools
- [x] Allow bob to see image attachments without throwing errors for invalid images or other attachments
- [x] Feed images into an image-to-text tool, or try a multi-modal model
- [x] Consider whether or not to migrate to Python (Answer: No, this is good.)
- [x] Setup TypeScript, ESLint, and Prettier following https://typescript-eslint.io/getting-started/
- [x] Setup testing and CI / CD with Github and Vitest following https://vitest.dev/
- [x] Cleanup/move repository from Heroku to Github, then deploy to Heroku
- [x] Archive the JS/TS repository for good code style practice, and start again in a new Python repo
