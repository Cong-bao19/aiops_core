import asyncio
import httpx
import time
import pandas as pd
import ast
import random
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm.asyncio import tqdm_asyncio
from sklearn.metrics import classification_report, confusion_matrix
from math import pi


SEED = 42
random.seed(SEED)
np.random.seed(SEED)


AI_MODELS = {
    "LogRobust (Upgrade)": "http://localhost:8000/stream_and_analyze",
    "LogRobust (Basic)": "http://localhost:8003/stream_and_analyze",
    "CNN Baseline": "http://localhost:8001/stream_and_analyze",  
    "Random Forest": "http://localhost:8002/stream_and_analyze"  
}

DATA_FILE_PATH = "test_readable.csv"


def prepare_balanced_test_data(df: pd.DataFrame, total_traces: int = 500):
    traces_by_label = {0: [], 1: [], 2: [], 3: []}
    
    for index, row in df.iterrows():
        try:
            label = int(row['Label'])
            if label not in traces_by_label: continue
            
            log_list = ast.literal_eval(row['Content'])
            raw_text = "\n".join(log_list)
            
            event_id_str = " ".join([str(e) for e in ast.literal_eval(row['EventId'])])
            
            event_templates = ast.literal_eval(row['EventTemplate'])
            time_deltas = ast.literal_eval(row['TimeDelta'])
            
            traces_by_label[label].append({
                "trace_id": row['SessionId'], 
                "text": raw_text, 
                "event_ids": event_id_str,
                "event_templates": event_templates, 
                "time_deltas": time_deltas,         
                "label": label 
            })
        except Exception:
            continue

    target_counts = {
        0: int(total_traces * 0.40),
        1: int(total_traces * 0.20),
        2: int(total_traces * 0.20),
        3: int(total_traces * 0.20)
    }
    
    final_test_set = []
    for lbl, target in target_counts.items():
        available = len(traces_by_label[lbl])
        take_n = min(target, available) 
        final_test_set.extend(random.sample(traces_by_label[lbl], take_n))

    random.shuffle(final_test_set)
    return final_test_set


async def test_single_model(client: httpx.AsyncClient, model_name: str, api_url: str, test_data: list):
    start_time_e2e = time.time()
    sem = asyncio.Semaphore(10)

    y_true = []
    y_pred = []
    model_latencies = []

    async def fetch(item):
        async with sem:
            try:
                payload = {
                    "trace_id": item["trace_id"], 
                    "raw_text": item["text"],
                    "event_ids": item["event_ids"],
                    "event_templates": item["event_templates"], 
                    "time_deltas": item["time_deltas"]          
                }
                
                req_t0 = time.perf_counter() 
                
                response = await client.post(api_url, json=payload, timeout=20.0)
                
                req_t1 = time.perf_counter() 
                
                if response.status_code == 200:
                    data = response.json()
                    pred_code = data.get("diagnosis_code", 0) 
                    
                    y_true.append(item["label"])
                    y_pred.append(pred_code)
                    
                    latency = data.get("latency_ms", 0)
                    if latency > 0:
                        model_latencies.append(latency)
                    else:
                        fallback_latency = (req_t1 - req_t0) * 1000 
                        model_latencies.append(fallback_latency)
            except Exception:
                pass 

    tasks = [fetch(item) for item in test_data]
    await tqdm_asyncio.gather(*tasks, desc=f"🤖 Benchmarking {model_name: <25}")
    
    total_time_e2e = time.time() - start_time_e2e
    
    if not y_true:
        return {
            "Model": model_name, "Accuracy": 0, "Precision": 0, 
            "Recall": 0, "F1-Score": 0, "Time_E2E(s)": 0, 
            "Avg_Inference_Time(ms)": 0, "y_true": [], "y_pred": []
        }

    report = classification_report(y_true, y_pred, output_dict=True, zero_division=0)
    
    accuracy = report.get('accuracy', 0) * 100
    macro_precision = report.get('macro avg', {}).get('precision', 0) * 100
    macro_recall = report.get('macro avg', {}).get('recall', 0) * 100
    macro_f1 = report.get('macro avg', {}).get('f1-score', 0) * 100
    
    avg_inference_ms = np.mean(model_latencies) if model_latencies else 0.0

    return {
        "Model": model_name,
        "Accuracy": accuracy,
        "Precision": macro_precision, 
        "Recall": macro_recall,
        "F1-Score": macro_f1,
        "Time_E2E(s)": total_time_e2e,
        "Avg_Inference_Time(ms)": avg_inference_ms,
        "y_true": y_true, 
        "y_pred": y_pred
    }

def draw_benchmark_chart(results):
    df = pd.DataFrame(results)

    my_palette = {
        "LogRobust (Upgrade)": "#2ca02c",  
        "LogRobust (Basic)": "#9467bd",       
        "CNN Baseline": "#ff7f0e",              
        "Random Forest": "#1f77b4"              
    }

    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle("AIOps RCA MULTI-CLASS BENCHMARK DASHBOARD", fontsize=24, fontweight='bold', y=0.98)

    ax1 = plt.subplot(2, 2, 1, polar=True)
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    N = len(metrics)
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1] 

    ax1.set_theta_offset(pi / 2)
    ax1.set_theta_direction(-1)
    plt.xticks(angles[:-1], metrics, size=12, fontweight='bold')
    ax1.set_rlabel_position(0)
    plt.yticks([20, 40, 60, 80, 100], ["20","40","60","80","100"], color="grey", size=10)
    plt.ylim(0, 100)

    for i, row in df.iterrows():
        values = row[metrics].values.flatten().tolist()
        values += values[:1]
        model_name = row['Model']
        color = my_palette.get(model_name, "#333333") 
        ax1.plot(angles, values, linewidth=2, linestyle='solid', label=model_name, color=color)
        ax1.fill(angles, values, color=color, alpha=0.15)
    ax1.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
    ax1.set_title("1. Comprehensive Performance (Radar Chart)", size=16, fontweight='bold', pad=20)

    ax2 = plt.subplot(2, 2, 2)
    df_melted = df.melt(id_vars="Model", value_vars=metrics, var_name="Metric", value_name="Score (%)")
    sns.barplot(data=df_melted, x="Metric", y="Score (%)", hue="Model", palette=my_palette, ax=ax2)
    for p in ax2.patches:
        height = p.get_height()
        if height > 0:
            ax2.annotate(f'{height:.1f}', (p.get_x() + p.get_width() / 2., height),
                         ha='center', va='bottom', xytext=(0, 3), textcoords='offset points', fontsize=11, fontweight='bold')
    ax2.set_title("2. Detailed RCA Metrics (Macro Avg)", size=16, fontweight='bold', pad=15)
    ax2.set_ylabel("Score (%)", fontsize=12, fontweight='bold')
    ax2.set_xlabel("")
    ax2.set_ylim(0, 119)
    ax2.legend_.remove() 

    ax3 = plt.subplot(2, 2, 3)
    current_markers = ["o", "s", "D", "^", "v"][:len(df)]
    y_col = "Avg_Inference_Time(ms)" if df["Avg_Inference_Time(ms)"].sum() > 0 else "Time_E2E(s)"
    
    sns.scatterplot(data=df, x=y_col, y="F1-Score", hue="Model", s=400, palette=my_palette, style="Model", markers=current_markers, ax=ax3)
    for i, row in df.iterrows():
        ax3.annotate(row['Model'], (row[y_col], row['F1-Score']),
                     xytext=(15, -5), textcoords='offset points', fontsize=12, fontweight='bold')
    title_suffix = "Model Inference (ms)" if y_col == "Avg_Inference_Time(ms)" else "HTTP E2E (s)"
    ax3.set_title(f"3. Trade-off: {title_suffix} vs Macro F1-Score", size=16, fontweight='bold', pad=15)
    ax3.set_xlabel(f"{title_suffix} -> (Lower is better)", fontsize=12, fontweight='bold')
    ax3.set_ylabel("Macro F1-Score (%) -> (Higher is better)", fontsize=12, fontweight='bold')
    ax3.legend_.remove()

    ax4 = plt.subplot(2, 2, 4)
    sns.barplot(data=df, x=y_col, y="Model", hue="Model", palette=my_palette, ax=ax4, legend=False)
    for p in ax4.patches:
        width = p.get_width()
        if width > 0:
            unit = "ms" if y_col == "Avg_Inference_Time(ms)" else "s"
            ax4.annotate(f'{width:.2f} {unit}', (width, p.get_y() + p.get_height() / 2.),
                         ha='left', va='center', xytext=(5, 0), textcoords='offset points', fontsize=13, fontweight='bold', color='red')
    ax4.set_title(f"4. Processing Speed ({title_suffix})", size=16, fontweight='bold', pad=15)
    ax4.set_xlabel(title_suffix, fontsize=12, fontweight='bold')
    ax4.set_ylabel("")

    plt.tight_layout()
    plt.subplots_adjust(top=0.90) 
    plt.savefig("benchmark_rca_dashboard.png", dpi=300, bbox_inches="tight")
    print("\n[SAVED] Dashboard exported successfully to 'benchmark_rca_dashboard.png'!")



async def main():
    print(" Loading data and generating RCA Benchmark scenario...")
    try:
        df = pd.read_csv(DATA_FILE_PATH)
    except Exception as e:
        print(f" Error reading data file: {e}")
        return

    test_data = prepare_balanced_test_data(df, total_traces=500)
    print(f" Scenario ready: Firing {len(test_data)} Traces into models.\n")

    results = []
    async with httpx.AsyncClient() as client:
        for model_name, url in AI_MODELS.items():
            try:
                await client.get(url.replace("/stream_and_analyze", "/docs"), timeout=2.0)
                res = await test_single_model(client, model_name, url, test_data)
                results.append(res)
            except Exception as e:
                print(f" Skipping {model_name} (Connection Failed. Is the port open?)")

    if not results:
        print("\n No models responded!")
        return

    print("\n" + "="*115)
    print(f"{'AI MODEL':<26} | {'ACCURACY':<10} | {'MACRO PREC':<10} | {'MACRO REC':<10} | {'MACRO F1':<10} | {'HTTP E2E(s)':<12} | {'MODEL INF(ms)':<12}")
    print("-" * 115)
    for r in results:
        print(f"{r['Model']:<26} | {r['Accuracy']:>8.2f}% | {r['Precision']:>8.2f}% | {r['Recall']:>8.2f}% | {r['F1-Score']:>8.2f}% | {r['Time_E2E(s)']:>10.2f} s | {r['Avg_Inference_Time(ms)']:>10.2f} ms")
    print("="*115)

    csv_data = [{k: v for k, v in r.items() if k not in ["y_true", "y_pred"]} for r in results]
    pd.DataFrame(csv_data).to_csv("benchmark_rca_results.csv", index=False)
    print(" [SAVED] Raw data exported to 'benchmark_rca_results.csv'")

    num_models = len(results)
    cols = 2
    rows = (num_models + 1) // 2
    fig, axes = plt.subplots(rows, cols, figsize=(14, 6 * rows))
    fig.suptitle("Confusion Matrices - RCA Multi-class", fontsize=20, fontweight='bold')
    
    if num_models == 1: axes = np.array([axes])
    axes_flat = axes.flatten()

    class_names = ['Normal', 'Delay', 'Exception', 'Truncation']

    for i, r in enumerate(results):
        ax = axes_flat[i]
        cm = confusion_matrix(r['y_true'], r['y_pred'], labels=[0, 1, 2, 3])
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax, 
                    xticklabels=class_names, yticklabels=class_names)
        ax.set_title(f"Model: {r['Model']}", fontweight='bold')
        ax.set_ylabel('True Label')
        ax.set_xlabel('Predicted Label')

    for j in range(i + 1, len(axes_flat)):
        fig.delaxes(axes_flat[j])

    plt.tight_layout()
    plt.savefig("benchmark_rca_confusion_matrices.png", dpi=300)
    print(" [SAVED] Confusion Matrices exported to 'benchmark_rca_confusion_matrices.png'")

    draw_benchmark_chart(results)

if __name__ == "__main__":
    asyncio.run(main())