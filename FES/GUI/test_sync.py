from collections import deque

acc = {
    "shank": deque([1, 2, 3, 4, 5]),
    "thigh": deque([1, 2, 3, 4, 5]),
    "foot": deque([1, 2, 3]) # foot is slower
}

def _drain_pairs(q1, q2):
    n = min(len(q1), len(q2))
    return [q1.popleft() for _ in range(n)], [q2.popleft() for _ in range(n)]

thigh_s, shank_for_knee = _drain_pairs(acc["thigh"], acc["shank"])

n_ankle = min(len(shank_for_knee), len(acc["foot"]))
foot_s = [acc["foot"].popleft() for _ in range(n_ankle)]
shank_for_ankle = shank_for_knee[:n_ankle]

print(f"thigh left: {list(acc['thigh'])}")
print(f"shank left: {list(acc['shank'])}")
print(f"foot left: {list(acc['foot'])}")
