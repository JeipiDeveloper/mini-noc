# Interview prep — the questions this project prepares you for

Answer in 3–6 sentences. Use the project as the example, then generalize. Do not memorize; understand the chain.

## Networking

**1. What happens when you type `http://app.local` and press Enter?**
The client asks CoreDNS (172.28.10.53) for an A record and gets 172.28.10.10. It opens a TCP connection to port 80 on nginx. nginx serves `/healthz` directly, or proxies `/api/*` to the API on the backend subnet. The API opens a short-lived Postgres connection and returns JSON. In a real environment there would be TLS between TCP and HTTP, and a load balancer before nginx.

**2. How does DNS resolution work?**
The resolver checks its cache, then queries the authoritative server for the zone. Here CoreDNS is authoritative for `*.local` and forwards everything else to 1.1.1.1. I can break resolution independently by stopping the `dns` container, which is why the DNS probe targets the resolver by IP instead of by name.

**3. TCP vs UDP?**
TCP is connection-oriented, ordered and retransmits; UDP is connectionless and does not. DNS uses UDP for small queries and TCP for large responses or zone transfers. My TCP probe only checks the handshake on 5432, which is enough to prove the database is accepting connections.

**4. What is a /24? Why two subnets?**
A /24 has 256 addresses, 254 usable. I used one for users/edge/monitoring and one for the API/database. The client lives only on the first; Docker's bridge isolation blocks it from reaching Postgres directly, so the only path is through nginx. It is a simplified DMZ model, not real VLAN tagging.

**5. What is NAT, and do you use it?**
NAT rewrites source addresses so private hosts can share a public address. Docker does this for outbound container traffic. Inside the lab, the two bridge networks are isolated, so the interesting traffic is east-west and does not need NAT; only the published ports reach the host.

**6. What is BGP? Have you used it?**
BGP is the path-vector protocol that exchanges routes between autonomous systems. I have not run it in this project — the honest answer is that the lab uses static Docker networks, and BGP with FRR/containerlab is the next milestone. I can explain the concepts (AS, peering, best path, failover) but I will not claim operational experience.

**7. How do you troubleshoot "the site is slow"?**
Break the time down with `curl -w` into DNS, TCP connect, time to first byte and total. Then test the API directly, then the database. In the project I also check `tc qdisc` because a previous chaos run may have left netem configured. I do not restart anything until I know which layer is slow.

## Observability

**8. Metric, log, trace — what is the difference?**
A metric is a number over time (probe duration), a log is a discrete event with detail (nginx error), a trace follows one request across services. This project uses metrics for detection, logs for diagnosis, and no tracing — which is a stated limitation.

**9. What is an SLI, SLO and error budget?**
SLI is the measured indicator (successful probes / total). SLO is the target (99.5% over 30 days). Error budget is what the target allows you to fail (about 3 h 36 min). Alerts should be tied to budget burn, not to feelings.

**10. How did you reduce alert noise?**
Three mechanisms: a `for` window so a single failed scrape does not page; grouping by cluster and severity so one event produces one webhook; and inhibition so a DNS failure suppresses `WebDown` and `ApiDegraded`, which are symptoms. The result was one ticket per root cause in all four game days.

**11. Why 1 minute for availability and 2 for latency?**
Detection time is roughly `for + scrape + group_wait`. One minute is long enough to ignore a single failed scrape and short enough to stay inside the budget. Latency is noisier, so two minutes avoids paging on one slow request. The measured consequence is 90 s versus 153 s to ticket; the trade-off is written in ADR 004.

**12. What if the alert fires but the service is fine?**
First question: is the probe lying? Check the probe's target, DNS, and whether the blackbox container itself is healthy. Then check for a partial failure the probe sees but users do not. If it is a false positive, fix the probe or the threshold and document why.

**13. How do you know the database is the problem and not the API?**
Layered probes: TCP to 5432, HTTP to `/api/status`, HTTP to `/healthz`. If TCP fails, the database is unreachable. If TCP is fine but `/api/status` returns 503, the API cannot use the database. If both are fine but `/healthz` fails, the edge is the problem.

## Operations

**14. What is a runbook?**
A short, tested procedure for one alert: what it means, the first commands, a decision tree, safe remediation, verification and escalation. In this repo every paging alert has one, and the ticket links to it automatically.

**15. What is a blameless postmortem?**
A factual timeline and root-cause analysis focused on systems, not people, with action items that have owners and dates. The goal is to change the system so the same failure is less likely or less damaging.

**16. What is MTTD and MTTR?**
Mean time to detect and mean time to recover. I measured time-to-ticket per scenario (90–153 s). I do not claim an MTTR: in a game day I control the recovery, so the number would be meaningless. That distinction matters in an interview.

**17. Tell me about a mistake you made.**
The first version of the alert routing used a 2-minute `group_interval`, so the resolved notification arrived two minutes after recovery. I found it in the first game day, measured it, reduced it to 30 seconds, and wrote the reason in the postmortem. The lesson: notification latency is part of the incident.

## Systems

**18. Container vs virtual machine?**
A VM virtualizes hardware and runs a full kernel; a container shares the host kernel and isolates processes with namespaces and cgroups. Containers are lighter and faster to start, but weaker isolation. Everything in this lab is a container, which is also a limitation for emulating routers.

**19. What is infrastructure as code?**
Describing infrastructure in versioned files so it can be reviewed, reproduced and rolled back. This project is partly IaC: Compose, Prometheus rules, Grafana provisioning and the Corefile are all code. It is not Terraform, and I say so; Terraform for the host and cloud resources is on the roadmap.

**20. How would you monitor 1,000 servers?**
Same model, different scale: consistent labels, service discovery instead of static targets, recording rules for expensive queries, retention and remote storage, and alert routing by team. The hard parts are cardinality and ownership, not the number of targets.

## Questions to ask the interviewer

- What does the on-call rotation look like, and who owns a ticket after escalation?
- Which alerts cause the most noise today, and what have you tried?
- Is there a runbook culture, or is knowledge in people's heads?
- How are changes correlated with incidents?
- What does success look like for an intern in the first 30 days?
