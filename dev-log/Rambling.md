

### Dev Updates
---

I've been busy, to say the least. This is a stab at pigeonisp in a cross-platform and slightly more absurd take to shake loose issues with my k8s integration and the idiocy of thinking I can have users manage their own ephemeral k8s clusters. Gonna be fun.

Unfortunately the youtrack instance with my original tickets and tracking notes was torn down (I got busy). It was feature-creeping something fierce. I did figure out that there are a few fun things you can do since then, like using Discord for an IDP and enabling SSO with k8s where you log in with... discord. Also GPUs in k8s, and AI - oh my.

I've been working with an engineer that inspired me to make this MIT and just dump it publicly (thanks James~).

I'm hoping to abuse Claude a fair amount to update my rough scripts into something shareable, I want to finish my CNI and make it self-heal. Way too much jank in my old demo videos.

I have plans again~

--

Okay I have a basis for setting up weird mesh networks in an extremely DIY format, in addition I was introduced to this project: https://netbird.io/

Seems interesting, it looks like the secure version of what I am poking at with a fleshed out NAT penetrator, and talos just starting supporting it natively. Womp womp. That said it has a bunch of features that would be great to have like SSO, I am immensely amused with the idea that to join the cluster you need to have a discord role.

Made the viz tool live under k8s/apps/flock-manager