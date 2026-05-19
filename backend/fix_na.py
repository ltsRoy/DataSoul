import re

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find patterns like:  var = something.sum()
    # and we want to ensure it's not pd.NA when evaluated
    # The easiest way is to add a helper function at the top and replace .sum()
    
    # Actually, we can just replace:
    # `if (expr) > 0:` with `if pd.notna(expr) and (expr) > 0:`
    # But it's hard to catch them all.
    
    # Let's replace: `.sum()` with `.fillna(False).sum()` for boolean masks?
    # No, some are sum over numbers: `.isna().sum()` which is always int.
    # The problem is ONLY with StringDtype/BooleanDtype `.str.contains` and `.str.match` which return BooleanDtype.
    
    # Let's replace `.str.match(..., na=False).sum()` with `.str.match(..., na=False).fillna(False).sum()`
    content = content.replace('.str.match(pct_pattern, na=False).sum()', '.str.match(pct_pattern, na=False).fillna(False).sum()')
    content = content.replace('.str.match(phone_pattern, na=False).sum()', '.str.match(phone_pattern, na=False).fillna(False).sum()')
    content = content.replace('.str.match(indian_pattern, na=False).sum()', '.str.match(indian_pattern, na=False).fillna(False).sum()')
    content = content.replace('.str.match(western_pattern, na=False).sum()', '.str.match(western_pattern, na=False).fillna(False).sum()')
    
    # Also replace .str.contains(...).sum() -> .str.contains(...).fillna(False).sum()
    content = re.sub(r'\.str\.contains\((.*?)\)\.sum\(\)', r'.str.contains(\1).fillna(False).sum()', content)
    
    # Also replace isin(...).sum() -> isin(...).fillna(False).sum()
    content = re.sub(r'\.isin\((.*?)\)\.sum\(\)', r'.isin(\1).fillna(False).sum()', content)
    
    # Also fix where we do > 0 checks directly on sum()
    # `if count > 0:`
    content = re.sub(r'if (\w+) > 0:', r'if pd.notna(\1) and \1 > 0:', content)
    
    # `if match_ratio < 0.4:`
    content = re.sub(r'if (\w+) < (0\.\d+):', r'if pd.isna(\1) or \1 < \2:', content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        
fix_file("f:/Antigravity Projects/DataSoul/backend/data_cleaners.py")
fix_file("f:/Antigravity Projects/DataSoul/backend/csv_corrector.py")
