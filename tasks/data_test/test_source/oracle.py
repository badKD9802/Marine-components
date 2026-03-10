try:
    import oracledb

    print(f"'oracledb' 설치됨  (버전: {oracledb.__version__})")
except ImportError:
    print(" 'oracledb' 라이브러리가 설치되지 않았습니다.")
