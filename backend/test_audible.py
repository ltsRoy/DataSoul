import sys, os
sys.path.append(os.path.abspath('.'))
from pipeline_engine import IterativePipeline
import pandas as pd

df = pd.read_csv('uploads/027694a5_audible_uncleaned.csv')
session = {'df': df}
pipeline = IterativePipeline()
print('Starting auto_clean on audible_uncleaned.csv...')
result = pipeline.auto_clean(session)

final_df = session['df_transformed']
print('\nOriginal Shape:', df.shape)
print('Cleaned Shape:', final_df.shape)

print('\n=== Audit Trail ===')
for a in result.get('audit', []):
    action = a["action"]
    detail = a["detail"]
    print(f'  [{action}] {detail}')

print('\n=== time column ===')
print('dtype:', final_df['time'].dtype)
print(final_df['time'].head(10).to_string())

print('\n=== author column (first 5) ===')
print('dtype:', final_df['author'].dtype)
print(final_df['author'].head(5).to_string())

print('\n=== stars column (first 10) ===')
print('dtype:', final_df['stars'].dtype)
print(final_df['stars'].head(10).to_string())

print('\n=== price column ===')
print('dtype:', final_df['price'].dtype)
print(final_df['price'].head(10).to_string())
