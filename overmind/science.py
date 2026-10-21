"""Inspect recorded evidence only; never silently rerun a held-out evaluation."""
import math


def wilson(correct,total):
    if not total:return None
    z=1.959963984540054
    p=correct/total
    middle=(p+z*z/(2*total))/(1+z*z/total)
    half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/(1+z*z/total)
    return [max(0,middle-half),min(1,middle+half)]


def failures(baseline,candidate):
    if len(baseline['results'])!=len(candidate['results']):raise ValueError('Evaluation lengths differ.')
    groups={name:[] for name in ('regressions','improvements','persistent_failures')}
    for b,c in zip(baseline['results'],candidate['results']):
        if (b['input'],b['target'])!=(c['input'],c['target']):raise ValueError('Evaluation examples do not align.')
        category=('regressions' if b['correct'] else 'persistent_failures') if not c['correct'] else ('improvements' if not b['correct'] else None)
        if category:groups[category].append({'input':c['input'],'target':c['target'],'baseline':b['prediction'],'candidate':c['prediction']})
    return groups


def compare(store,left,right):
    a,b=store.read(left,'report.json'),store.read(right,'report.json')
    comparable=a['dataset_sha256']==b['dataset_sha256'] and a['method']==b['method']
    output={'left':left,'right':right,'same_dataset_and_method':comparable,
            'notice':'Descriptive comparison of recorded results. Reusing the same holdout is exploratory; these intervals are not a new promotion test.',
            'results':[]}
    for rid,report in ((left,a),(right,b)):
        test=store.read(rid,'candidate-test.json')
        correct=sum(row['correct'] for row in test['results'])
        output['results'].append({'id':rid,'method':report['method'],'baseline_accuracy':report['baseline_accuracy'],
                                  'candidate_accuracy':report['candidate_accuracy'],'correct':correct,'count':test['count'],
                                  'accuracy_wilson_95':wilson(correct,test['count']),'promoted':report['promoted'],
                                  'dataset_sha256':report['dataset_sha256'],'candidate_sha256':report['candidate_sha256']})
    output['accuracy_difference']=b['candidate_accuracy']-a['candidate_accuracy'] if comparable else None
    if not comparable:output['warning']='Different dataset fingerprints or methods: no fair score difference is reported.'
    return output


def loss_chart(metrics,width=600,height=200):
    """SVG chart from persisted epoch loss; no fabricated interpolation or live animation."""
    if not metrics:return None
    margin=38;plot_w=width-margin-15;plot_h=height-2*margin
    peak=max(m['loss'] for m in metrics) or 1
    max_epoch=max(m['epoch'] for m in metrics)
    points=[(margin+plot_w*(m['epoch']-1)/max(1,max_epoch-1),height-margin-plot_h*m['loss']/peak) for m in metrics]
    ticks=''.join(f'<text x="2" y="{height-margin-plot_h*v+4:.1f}">{peak*v:.2f}</text><path d="M{margin} {height-margin-plot_h*v:.1f}h{plot_w}" stroke="#34463c"/>' for v in (0,.5,1))
    dots=''.join(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="#b8ffad"/>' for x,y in points)
    line=' '.join(f'{x:.2f},{y:.2f}' for x,y in points)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="#0c1911"/><g fill="#bbd8c0" font-family="monospace" font-size="11"><text x="{margin}" y="18">RECORDED TRAINING LOSS · mean cross entropy</text>{ticks}<polyline points="{line}" fill="none" stroke="#8bdba0" stroke-width="2"/>{dots}<text x="{margin}" y="{height-12}">Epoch 1</text><text x="{width-100}" y="{height-12}">Epoch {max_epoch}</text></g></svg>'
