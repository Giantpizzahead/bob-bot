This is a list of ideal features, along with which are currently implemented.

## Ideal Features

### Discord Text

- [x] Detect when Bob is pinged (DM, direct ping, or name), and differentiate that from just a new message.
- [x] Be able to remember a short conversation history (last 6 non-command messages truncated to last 128 tokens, not including current one), for context.
- [ ] ~~Make a running summary / status report of what Bob is talking about (and with who), shared across server and DMs.~~
- [x] Be able to see if someone is currently typing (ex: to decide whether to respond or not).
- [x] Be able to see if the message was sent as a reply to another message.
- [x] Be able to see if a previous or current message was edited (ex: right before sending a response).
- [x] Be able to remember deleted messages (if Bob saw them before).
- [x] Be able to see image attachments.
- [x] Let Bob decide whether to look at the message based on whether he was pinged.
- [x] Let Bob decide whether to send messages as a reply.
- [x] Query external tools (web search, image search, reasoning, mood, etc) to determine a good reply.
- [x] Give a reply in Discord's writing/humor style.
- [x] Be fine and open with NSFW messages and replies.
- [x] Still, send all messages with the intention of ensuring everyone has a good time.

### Voice Chat

- [x] Be able to join and leave VCs.
- [x] Be able to hear people in VC (using Whisper or similar).
- [x] Be able to speak reasonably well in VC (using smart TTS tools).
- [x] Be able to respond to someone else in real time (similar to human response time).
- [ ] ~~Recognize when Bob should talk (being called on or period of silence, don't try to interrupt).~~
- [ ] ~~Talk in a style that's appropriate for Discord VCs.~~
- [ ] ~~Query external tools in the background to determine good replies.~~
- [ ] ~~Be able to work with other portions of the bot (ex: what Bob says/hears in VC should influence his mood, what he types in text chat, etc.).~~

### Human-like

- [x] Have a semi-persistent mood. (Side effect of conversation history)
- [x] Know what Bob (himself) is doing at the moment, and factor that in when sending messages.
- [ ] ~~Have desires (ex: to make/hang out with friends), and factor that in when making decisions.~~
- [x] Learn about people through their real names, as opposed to Discord handles (only care about handles when immediately relevant).
- [x] Be able to store and recall facts and tidbits about people/events through long-term memory.
- [ ] ~~Consolidate long-term memory as needed to maintain effective recall.~~
- [ ] ~~Understand its relationship with other people (ex: whether they're strangers or friends).~~
- [x] Do tasks normal humans do - sleep, eat, do some work/classes, etc. don't just be terminally online.
- [ ] ~~Choose when to do these tasks, potentially asking friends to join or joining friends.~~
- [x] Understand college-level and/or server-specific slang and jokes without needing to do a web search.
- [ ] ~~Have a deep, consistent life background and writing style. Stick to it.~~
- [x] Do not give misleading info. Do not lie with malicious intent.

### Tools

- [x] Know the current time and date.
- [x] Be able to search the web for up-to-date content, look for relevant images, and do reverse image search.
- [x] Be able to roughly understand YouTube videos/shorts (ex: through their transcripts).
- [ ] ~~Be able to reason through complex problems through multi-step LLM thought processes.~~
- [ ] ~~Have access to a code interpreter to help with solving complex problems (ex: calculator).~~
- [ ] ~~Be able to choose to read/send messages, join/leave VCs, and play games as needed.~~

### Gaming

- [x] Be able to join a Chess.com match (in regular chess, possibly timed) using an invite link.
- [x] Play chess at a configurable level of difficulty (anything is fine).
- ~~[ ] Be able to join a Skribbl.io match using an invite link.~~
- [ ] ~~Be able to guess a word sometimes, given someone else's drawing and the guesses so far.~~
- [ ] ~~Be able to draw a word well enough such that others can guess it sometimes, given a vector art image of the word. Stop drawing when the round ends.~~
- [ ] ~~Extra: Use OCR of some sort to filter out words in the image that may give away the answer. Or, start drawing related text if no one guesses the image.~~
- [ ] ~~Be able to join a League of Legends lobby when being sent an invite.~~
- [ ] ~~Be able to play games of Coop vs. AI as a solo mid laner with one champ, on Beginner difficulty.~~
- [ ] ~~Be able to play games of Coop vs. AI as a duo bot lane with one champ, on Beginner difficulty.~~

### Ease of Use

- [x] Have a default mode which incorporates all the above features.
- [x] Have an obedient mode which heavily encourages the bot to honor any request people make of it.
- [x] Have an off mode that turns the bot off. No requests of any sort should be made during this time.
- [ ] ~~Create a simple web interface for debugging and/or tuning core features without needing to reboot.~~

### Efficiency

- Almost all LLM requests should be tied to a Discord message. Periodic updates should happen at most once every 1-2 hours.
- Prompts and repsonses between agents should try to keep token use low.
- Keep the system simple to think about, avoid adding too many agents.
