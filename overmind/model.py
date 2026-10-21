"""CPU softmax linear neural text classifier. Genuine SGD weight updates, no ML dependency."""
import hashlib
import math
import random
import re
from collections import Counter

class TextStudent:
    kind = 'weight_training'
    def __init__(self, labels, dimensions=2048, weights=None):
        self.labels = labels
        self.dimensions = dimensions
        self.weights = weights or [[0.0] * dimensions for _ in labels]
        self.optimizer_steps = 0
        self.last_epoch = {}

    def features(self, text):
        words = re.findall(r"[a-z0-9]+", text.lower())
        tokens = words + [' '.join(pair) for pair in zip(words,words[1:])]
        # Character features offer limited robustness to inflections.
        tokens += ['~'+word[i:i+3] for word in words for i in range(max(0,len(word)-2))]
        counts = Counter(1 + int.from_bytes(hashlib.blake2b(t.encode(),digest_size=4).digest(),'little') % (self.dimensions-1) for t in tokens)
        norm = math.sqrt(sum(v*v for v in counts.values())) or 1
        return {0:1.0, **{i:v/norm for i,v in counts.items()}}

    def probabilities(self, features):
        logits = [sum(w[i]*v for i,v in features.items()) for w in self.weights]
        high = max(logits)
        exp = [math.exp(v-high) for v in logits]
        return [v/sum(exp) for v in exp]

    def predict(self, text):
        p = self.probabilities(self.features(text))
        return self.labels[max(range(len(p)),key=p.__getitem__)]

    def epoch(self, rows, rate, seed, guard):
        rows = list(rows)
        random.Random(seed).shuffle(rows)
        loss = 0
        gradient_sum = 0
        for row in rows:
            guard()
            f = self.features(row['input'])
            p = self.probabilities(f)
            target = self.labels.index(row['target'])
            loss -= math.log(max(1e-15,p[target]))
            gradient_sum += math.sqrt(sum((p[c] - (c == target))**2 for c in range(len(p))) * sum(v*v for v in f.values()))
            for c,w in enumerate(self.weights):
                error = p[c] - (c == target)
                for i,v in f.items():
                    w[i] -= rate * error * v
            self.optimizer_steps += 1
        self.last_epoch = {"examples":len(rows), "mean_gradient_l2":gradient_sum/len(rows), "learning_rate":rate}
        return loss/len(rows)

    def export(self):
        return {'format':'overmind.softmax.v1','labels':self.labels,'dimensions':self.dimensions,'weights':self.weights,'optimizer_steps':self.optimizer_steps}

    @classmethod
    def restore(cls, artifact):
        if artifact.get('format') != 'overmind.softmax.v1':
            raise ValueError('Unsupported student artifact.')
        labels, dims, weights = artifact['labels'], artifact['dimensions'], artifact['weights']
        if not 2 <= len(labels) <= 32 or not 2 <= dims <= 8192 or len(weights) != len(labels) or any(len(w)!=dims or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in w) for w in weights):
            raise ValueError('Invalid student weights.')
        steps=artifact.get('optimizer_steps',0)
        if type(steps) is not int or steps<0:raise ValueError('Invalid optimizer-step counter.')
        model=cls(labels,dims,weights);model.optimizer_steps=steps
        return model
