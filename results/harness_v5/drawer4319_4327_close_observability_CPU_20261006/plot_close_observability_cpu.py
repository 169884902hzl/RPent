"""Export the saved-only close metrology scatter, including a boundary zoom."""

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


BASE = Path(__file__).resolve().parent
DATA = BASE / 'saved_close_measurements.jsonl'
GROUPS = [('original559_final100_close', 'Original 559 selection: final close'),
          ('4319_callback_close', '4319: contact callback frames'),
          ('4327_callback_close', '4327: frontmost callback frames')]


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


rows = [json.loads(line) for line in DATA.read_text().splitlines()]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'pdf.fonttype': 42})
fig, axes = plt.subplots(2, 3, figsize=(13, 7), constrained_layout=True)
plot_counts = {}
for col, (name, title) in enumerate(GROUPS):
    records = [row for row in rows if row['analysis_group'] == name]
    valid = [row for row in records if row['eligible_original_metrology'] and row['private_qpos_m'] is not None]
    plot_counts[name] = {'saved_samples': len(records), 'valid': len(valid), 'null': len(records)-len(valid),
                        'distinct_cases': len({row['case'] for row in records})}
    for index in (0, 1):
        ax = axes[index, col]
        for truth, color, marker, label in [(True, '#0072b2', 'o', 'Strict true'), (False, '#d55e00', 'x', 'Strict false')]:
            data = [row for row in valid if row['private_truth'] is truth]
            ax.scatter([-row['private_qpos_m']*1000 for row in data],
                       [row['signed_extension_m']*1000 for row in data],
                       c=color, marker=marker, s=34, alpha=.7, label=label)
        ax.axvline(0., color='#777777', linewidth=1, linestyle=':')
        ax.axhline(.5, color='#555555', linewidth=1, linestyle='--', label='Current public 0.5 mm')
        ax.grid(color='#dddddd', alpha=.5)
        if index == 0:
            ax.set(xlim=(-6, 170), ylim=(-15, 170), title=title)
            ax.text(.03, .96, f"{len(valid)}/{len(records)} valid; {len(records)-len(valid)} null\n{plot_counts[name]['distinct_cases']} distinct cases",
                    transform=ax.transAxes, va='top', fontsize=9)
        else:
            ax.set(xlim=(-3, 3), ylim=(-3, 3), title='Same data: strict-boundary zoom')
        ax.set_xlabel('Private reference -qpos (mm; scoring only)')
        if col == 0: ax.set_ylabel('Public signed extension (mm)')
axes[0, 0].legend(loc='lower right', fontsize=8)
axes[1, 1].annotate('Same signed +0.244 mm\nopposite strict labels', xy=(.113160769, .244140625),
    xytext=(.6, 1.7), arrowprops={'arrowstyle': '->', 'color': '#333333'}, fontsize=9)
fig.suptitle('Saved close endpoint observations: a scalar threshold cannot resolve all strict labels\n'
             'Callback frames are correlated; nulls remain null. Existing control threshold is unchanged.', fontsize=13)
png, pdf = BASE/'close_observability.png', BASE/'close_observability.pdf'
fig.savefig(png, dpi=180)
fig.savefig(pdf)
plt.close(fig)
metadata = {'producer': ref(Path(__file__)), 'input': ref(DATA), 'png': ref(png), 'pdf': ref(pdf),
            'plot_counts': plot_counts, 'private_used_for_control': False,
            'scope': 'Only originally eligible frames are plotted. Null and original case denominators are shown; zoom axes retain the same data.'}
(BASE/'close_observability_figure.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'png':ref(png),'pdf':ref(pdf),'plot_counts':plot_counts}))
