I started out with the vision to create a personal AI assistant that will know about the person using it end-to-end and can give suggestions, guidance and even be a substitute to him/her when asked by the user. 

And it fell apart pretty badly.

So I wanted an app where we have different modules about the user like his day-to-day activites, his habits, his plans and future goals, his buying activities and daily chores.
The app will also have an extensive collection of all the people the user knows, what connections the user has with each person, who they are related and whom to contact when to keep in touch and make sure the relation keeps on living.
I also wanted the assistant to have the capabilities of handling most or all of the normal actions a user performs on a general/periodic time period. (like buying grociers, renewing insurance, gas etc)

I also wanted it to be extensionable so that other developers can create and attach new modules seemlessly to the platform as their need requirments. And most importantly the user data should be imgratable or at least downloable if needed.
The assistant can look it up when needed and help the user when ever needed.

Well, the core idea was to create a digital duplicate of a physical persona and be able to do all the activities online that a normal person does. This pretty much attributes to the overall goal of winning death, as this too is a type of life extension.

Well the technologies already exist and so I thought what keeps me back? 

So I started with the first task of creating a to-do list where it can store all the data of the user in an interface with connectors to notion, google calendar, google people api and google email. 

Now the thing with AI coding agents is the context length and the amount of tokens it uses to code and debug. The debug takes a lot of tokens without being successful sometimes. 
So I split the project into layers like memory, input layer, the llm_module, Orchestrator layer etc. With each agent being responsible for each layer during the build, with communication given through spec.md, Contract.md and Implementation_guide.md.
Then an over-watcher agent to actually check if each of the layers work together without any problem.

In the first iteration I ended up building an app with ai api (gemini), but did not find it useful and extremely hard to iterate, test and extend.
So I restarted the project and wanted to build each layer extensively and spent too much time on the memory layer, failing to actually make it useful or test whatever I had built.
Then, I restarted the project again, with just the notion integration and google calendar and contacts integration. I this time only focused to build an to-do list similar to ticktick or asana. But later the notion integration for more specific CURD changes did not work properly. So I kind of removed it from the project to just focus on the larger idea. 

Now, I don't know where to focus on, or the architecture of the project or how to implement. But I only know what the end product should feel like.