This list will evolve as the bot progresses. We'll start getting features working, and add polish later.

## Current Tasks

### Today

#### General

- [ ] Make a demo showcasing all the cool features the bot has!

#### Voice

- [ ] Improve the VC prompt to make a better-sounding bot
- [ ] Make the bot say "filtered" if appropriate
- [ ] Implement better VC chatting logic (don't block on every new message, stop talking if a user is talking, etc)

#### Activities

- [ ] Allow Bob to auto-start chess and voice calls based on context

### Future

#### Voice

- [ ] Implement a more complete prompt that takes STT results, VC message history, and the channel's recent message history, integrating with tools if possible, to talk semi-well in voice chat

#### Activities

- [ ] Implement some sort of auto schedule planner that decides when Bob will do certain activities each day (by default, but Bob can override this)
- [ ] Figure out why the YouTube comment grabber works (and not PyTube), then try to use it to get the video's metadata and transcript
  - It looks like the issue is not the library. Instead, it's YouTube blocking proxies (which makes sense). We could try looking into [free](https://www.croxyproxy.com/) [proxies](https://www.webshare.io/features/free-proxy), which can be integrated into requests and PyTube. But the simpler option is likely to use YouTube's official API, which actually has reasonable daily quotas (we won't hit them with normal usage, maybe close with dev usage). See [here](https://github.com/sns-sdks/python-youtube) for a python library using it. I don't think trying to fix this right now makes sense, since YouTube will continue to change their blacklist/bot countering mechanisms.

#### Smarts

- [ ] Give Bob a code execution tool (as an advanced calculator or code debugging helper), see [here](https://rapidapi.com/onecompiler-onecompiler-default/api/onecompiler-apis)
- [ ] Give Bob a reverse image search tool (to look up where locations are, what show an image is from, etc), see [here](https://rapidapi.com/letscrape-6bRBa3QguO5/api/reverse-image-search1)
- [ ] Add a reasoning dummy tool with guided plan arguments, hard code it to send back a system message or something
- [ ] Consider giving Bob a Discord history tool to manually go back and find specific messages
- [ ] Implement a verifier agent that checks if the problem solving agent's context makes sense, given previous tool call results and what the verifier itself knows. Only needs checking if the reasoning tool was called. This verifier agent should use a different LLM model (sorta like manual mixture-of-experts). If not reasonable, delegate it back and keep iterating.
- [ ] Make the verifier interact with the problem solving agent in a single back-and-forth. If it fails verification once, send back to the problem solving agent with feedback. If it fails verification twice, send context to Bob saying that the problem solving agent couldn't figure out the answer, and to echo that uncertainty to the user (making clear that it's guessing).
- [ ] Add a view_image tool to see a given URL. Only enable it if no image is present already. Custom code it to basically send a success tool message then add human image, or if it can be direct in tool do that.

#### Memory

- [ ] Make a summarizer agent that can take in chat history and create a <= N-word summary, where N is a parameter that the user (caller) can control
- [ ] Make a memory agent that reads chat history and determines important factual memories to store. Memories can be rated by their significance (is it important to remember?), relevancy (will it come up later?) objectiveness (is it a fact?), and accuracy (is the info provably correct?) on scales of 1-10. Potentially split this up into 2 agents, one that generates the memory and one that does the ratings (a verifier).
  - Some good references to go off of: [This video demonstrating a ChatGPT-like readable long term memory system](https://www.youtube.com/watch?v=oPCKB9MUP6c), [this Github repo using hierarchical memory](https://github.com/kyb3r/emergent/blob/main/emergent/memory.py), and [the corresponding design document](https://github.com/daveshap/HierarchicalMemoryConsolidationSystem).
  - It looks like no specifically designed libraries exist for creating these memories, so let's build this up ourselves, potentially reusing other people's code, with citations.
- [ ] Use the memory agent to create candidate long-term memories. Then, before putting them in the vector store, retrieve similar memories that already exist, and combine them into a "knowledge base article" or similar.
  - We could potentially use [LlamaIndex](https://medium.com/llamaindex-blog/data-agents-eed797d7972f) to process the memories once we've created them. I'm not sure how this would fit together yet.
- [ ] Implement a memory pruning system that just prunes the Pinecone database, removing the oldest memories which haven't been retrieved/updated upon reaching a limit, or prunes memories that haven't been retrieved/updated for X days (maybe incremental, like spaced repetition retention times).

#### Text

- [ ] Optimize TextChannelHistory token usage by truncating messages
- [ ] Add medium-term memory to TextChannelHistory by summarizing long messages and those that go out of the window

#### Quality of Life

- [ ] Add URLs property to ParsedMessage that contains a list of all URLs present in a message (valid or not)
- [ ] Add a delayed second check on whether to send a message or not, to be ran when no one is typing and Bob decided not to respond before (due to not being sure if the other person was done). In this delayed check, emphasize to the decision agent that all users are done typing.
- [ ] Think of a way to fix sending multiple messages at once that does not involve the decision maker running again when Bob sent the last message (that doesn't work). Switching Bob's prompt to allow for multiple messages as a response doesn't work well. The best way likely involves a small LLM at the end deciding how to split up a long message into smaller messages, since this won't be influenced by history.
- [ ] Make a GIF creator on the server-side to improve the spectate command's frame rate
- [ ] Make a Discord status message based on current activity
- [ ] Make the chess bot better at checkmating and avoiding stalemates
- [ ] Make the chess prompt track the name of the user Bob is playing against (for better comments)
- [ ] Update exports from each module to generate better docs
- [ ] Make fake typing speed timing wait from when the last message was received, rather than when the final response has been determined
- [ ] Send image link, if a single one is present in AI's response, in a separate message (to hide the link)
- [ ] Allow for a custom Bob normal prompt using an environment variable
- [ ] Avoid starting speech to text connections for frivolous speech detections

## Completed Tasks

### General

- [x] Finally finish setting up the Python development environment
- [x] Plan out how Bob will be structured (at a high level) in V2
- [x] Attempt to use Crew.AI to build the V1 multiagent system (conclusion: Crew.AI sucks)
- [x] Attempt to use AutoGen to build something like the V1 multiagent system
- [x] Implement default and off modes, along with default and instant speeds
- [x] Reorganize by moving the bot and the agent into classes (for easier abstraction/usage) (decided not to do for now, instead put them in separate functions)
- [x] Make Bob easier to debug by allowing debug info to be printed on demand in Discord
- [x] Split big files (modules) into smaller, manageable modules while avoiding cyclic dependencies for ease of development
- [x] Make a command that reboots the bot on Heroku (just make the worker terminate)
- [x] Add tests for stable functions (that likely won't change)

### Text

- [x] Implement a class that abstracts away Discord text channel history/event handling
- [x] Improve TextChannelHistory to include details about replies, reactions, stickers, and attachments
- [x] Improve TextChannelHistory to include details about edited and deleted messages
- [x] Begin to optimize TextChannelHistory token usage by truncating messages based on how recent they are
- [x] (Re)implement a bare bones version of Bob by passing in message history with a simple system prompt and a single agent
- [x] Wait for users to finish typing before sending a message
- [x] Clean up message history class (OOP kinda sucks ngl)
- [x] Bring back the original Bob's chatting style, and keep it that way

### Multi-agent

- [x] Implement a basic chain: Response decision -> Message sender
- [x] Refine message quality and handle content filtering by testing different models
- [x] Basically the whole project is multi-agent so yeah

### Smarts

- [x] Implement a web search tool in the agents subpackage, splitting into files (modules) as needed for organization (try to avoid OOP/state)
- [x] Integrate web search into Bob's overall pipeline, with a problem solving agent that decides if tool calls are needed, returning any additional factual context to Bob (simplified by just putting the tools direclty into Bob's main agent)
- [x] Modify decision agent prompt to respond to things like "ty" or "gn", and modify Bob to only send 1 image/link at a time (except in extenuating circumstances), and only send 1 newline to split messages instead of 2
- [x] Let Bob know what the date is somehow, maybe through a tool, without him trying to search the exact date every time
- [x] Think about what to do when Bob is fed an image - probably shouldn't go through all the tools, right?
- [x] Give Bob a website scraping tool (ideally with something like Playwright for JS sites), see [here](https://python.langchain.com/v0.2/docs/integrations/tools/playwright/) and [here](https://python.langchain.com/v0.2/api_reference/_modules/langchain_community/tools/playwright/extract_text.html#ExtractTextTool).
  - Turns out this is more complicated than expected, because it also needs retrieval through RAG. I'm using [the JS version](https://github.com/langchain-ai/langchainjs/blob/b85e160b66d8ab09075aee1755efa0448a4aad52/langchain/src/tools/webbrowser.ts#L185) as a reference implementation.
- [x] Implement a system that switches to deepseek (model/prompt) when very edgy or NSFW responses are needed, can be detected using OpenAI's moderation API

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
- [x] Implement a way to force stop activities
- [x] Implement an overall status message that can be fed into Bob
- [x] Allow Bob to comment on current activities through the status message
- [x] Improve spectate command by editing image repeatedly, allowing a very low frame rate video
- [x] Fix the Chess.com player in some way to avoid bot detection (manually give it saved cookies, either through Heroku's exec SSH tool or with the new environment variable)
- [x] Add a "Done spectating" text of some sort when spectating is finished
- [x] Implement simulated work, sleep, eat, and shower activities
- [x] Fix YouTube video search on Heroku (unknown PyTube error), potentially needing [this](https://github.com/JuanBindez/pytubefix) since the pytube repo hasn't been updated in about a year now
- [x] Make a command to stop spectating, and a command to check the program's RAM usage
- [x] Fix memory leak and/or memory inefficiency issue with spectate (maybe save/load screenshots from a file instead, to avoid any possibility of leaking RAM)
- [x] Trigger Python garbage collection a lot while playing Chess and/or spectating to avoid memory limit issues (at the cost of speed, but not really since we get slowed due to memory)
- [x] Refamiliarize ourselves with the AlphaLoL codebase and think through the feasibility of directly converting it to use the Arduino mouse (start with this, don't jump!)
  - Actually, in the spirit of not trying to revive a done project with very little time left, and also to avoid tying the two projects together, we're not going to implement League stuff.

### Memory

- [x] Make a simple memory system that adds every tool call query and result, along with every message (or message pair), into a Pinecone vector store, then retrieves the top 3 or so to give directly as context to Bob in the first system prompt.
- [x] Improve the memory system by filtering based on either tool calls or chat history, having queries with different time ranges to weight recent messages more, and combining query variations to produce diverse memory results
- [x] Make a command to look up stored long term memories with a query, potentially choosing to filter with only tools
- [x] Make a command to delete a stored memory by ID, for manual cleanup if sensitive info gets leaked
- [x] Make an "incognito mode" where all attempts to save new memories are turned off (can still access and use old memories), also consider making !off and !on commands, does /mode make sense?
- [x] Check overall token usage from test suite, to get a sense of how much this overall system costs (we optimized a decent amount, so it shouldn't be too bad... right?)

### Voice

- [x] Figure out how to work with Discord voice calls, since discord.py's voice module got removed
- [x] Why is downsampling and working with audio formats so confusing??? Mark this complete when we being to sort of figure everything out
- [x] Implement a simple, robotic-sounding TTS system (Neurosama?)
- [x] Try using Azure's STT with Discord to get a voice-based chat history
- [x] Make or use a bare bones prompt that takes STT results and VC message history to talk decently in voice chat

## Milestones and Capstones

### Text

- [x] Have Bob send a hello world message in Discord (7/13/24)
- [x] Hold a decently intelligble conversation with someone (7/13/24)
- [x] Demonstrate flexibility by playing 20 questions (7/14/24)
- [x] Demonstrate emerging reasoning skills by identifying League champs (7/15/24)
- [x] Recognize and be able to vaguely discuss images (8/18/24)
- [x] Send multiple messages at once, or send no messages when appropriate in a non-hacky way (8/26/24)
- [x] Demonstrate improved knowledge by answering questions requiring real time (online) info (8/29/24)
- ~~[ ] Initiate a DM or group chat conversation after being inactive for a while~~
- ~~[ ] Have a persistent mood and/or life story through simulated emotions and events~~
- [x] Remember details about people from a long time ago, say >50 messages (8/31/24)
- ~~[ ] Understand the difference between DMs and servers, and participate in both of them~~
- [ ] **Capstone:** Hold an emotional and long (requiring memory) chat conversation in DMs while acting similar to a human
- [x] **Capstone:** Act like a normal, active Discord user in a medium sized server, replying to or initiating messages (9/1/24)

### Voice

- [x] Join voice chat and play some music (7/15/24)
- [x] Be able to respond intelligbly to someone talking in voice chat (7/18/24)
- ~~[ ] Respond in a more human-like voice~~
- [ ] Generate a response in near real-time, quick enough to not be awkward
- [ ] Integrate text chat capabilities (memory and reasoning) into voice chat
- [ ] **Capstone:** Participate decently in a group voice chat, in real-time!

### Gaming

- ~~[ ] Play League, a comprehensive, tough game with an anticheat~~
- [x] **Capstone:** Play Chess at a rating > 800, for an easy-to-play (ish) proof of concept (8/28/24)

### All Together

- [ ] **Capstone:** Ask Bob to join Discord voice chat, then ask in VC to play a game, then have him actually join and play that video game!

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
