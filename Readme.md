# Pigeon Game

What?

**https://www.youtube.com/@pigeonisp**

Oh.

Oh no.

```
On April 1st 1990 RFC1149 became a thing. 
This repo serves to see how far you can take that
specification and run with it using modern tooling
in place of live animals. Expect shenanigans.
```

# Project Status

![Alt Text](https://media1.tenor.com/m/si53c8wtxCAAAAAC/my-life-in-a-nutshell-sigh.gif)

Figuring out how to make unity play nice with bazel. Because ~~I'm a massochist~~ it will be great when it is working.


### Setup

//TODO



### Build instructions

//TODO



### Disclaimer
***
None of this is a good idea to expose to the actual internet.

None of this is safe to run with a stranger.

None of this really cares about best practices or security until there's a rough base. 
At that point I'll take an RBAC pass and drop in istio (or something equivalent). 
It still won't be safe.

If you have ideas for security, I'm all ears. I'm pretty sure with the premise of how I want to technically implement this idea - which yields having bare-metal cluster access via a game - is a recipe for getting root'd if you open this up to the internet with naive end-users copying and pasting w/e into a teminal until it 'works'

There's an aggressive amount of generated code, bad ideas, half-baked solutions, and general shenanigans in this repo. Tread lightly.

If you take anything out of this repo, if you run any scripts, if you attach something like cursor or claude, you do so at your own risk. It's all MIT - do what you want with it - just don't point at me when you have a bad time. You did this <3
***