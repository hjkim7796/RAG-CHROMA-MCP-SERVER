#!/usr/bin/env python3
"""
MCP HTTP Proxy (Python)
stdio를 HTTP/SSE로 변환하는 프록시
"""

import sys
import json
import requests
from urllib.parse import urljoin

# 설정
SERVER_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/sse"
DEBUG = True


def debug_log(*args):
    """디버그 로그"""
    if DEBUG:
        print("[MCP-PROXY]", *args, file=sys.stderr)


def send_http_request(message):
    """HTTP POST 요청 전송"""
    try:
        debug_log("Sending request:", json.dumps(message))
        
        response = requests.post(
            SERVER_URL,
            json=message,
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json'  # JSON으로 변경
            },
            timeout=60
        )
        
        response.raise_for_status()  # HTTP 에러 체크
        
        debug_log(f"Response status: {response.status_code}")
        debug_log(f"Response headers: {dict(response.headers)}")
        
        # 일반 JSON 응답 처리
        try:
            result = response.json()
            debug_log("Received JSON response:", json.dumps(result))
            return result
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 SSE 형식 시도
            debug_log("Not JSON, trying SSE format...")
            response_text = response.text
            debug_log(f"Response text: {response_text[:200]}")
            
            for line in response_text.split('\n'):
                if line.startswith('data: '):
                    json_data = line[6:]
                    try:
                        result = json.loads(json_data)
                        debug_log("Parsed SSE data:", json.dumps(result))
                        return result
                    except json.JSONDecodeError as e:
                        debug_log("SSE parse error:", e)
            
            raise Exception(f"Could not parse response: {response_text[:100]}")
            
    except requests.exceptions.Timeout:
        raise Exception("Request timed out - server may not be responding")
    except requests.exceptions.ConnectionError:
        raise Exception("Connection refused - is the server running at " + SERVER_URL + "?")
    except requests.exceptions.HTTPError as e:
        raise Exception(f"HTTP error {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        debug_log("Request error:", str(e))
        raise


def main():
    """메인 함수"""
    debug_log(f"MCP HTTP Proxy started, connecting to: {SERVER_URL}")
    
    try:
        # stdin에서 한 줄씩 읽기
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                # JSON 메시지 파싱
                message = json.loads(line)
                debug_log("Received from stdin:", json.dumps(message))
                
                # id를 문자열로 변환 (MCP는 string | number를 지원하지만 string이 더 안전)
                if "id" in message and message["id"] is not None:
                    message["id"] = str(message["id"])
                
                # HTTP 요청 전송 및 응답 받기
                response = send_http_request(message)
                
                # 응답의 id도 문자열로 변환
                if "id" in response and response["id"] is not None:
                    response["id"] = str(response["id"])
                
                # error 응답인 경우 id가 없으면 message의 id 사용
                if "error" in response and ("id" not in response or response["id"] is None):
                    if "id" in message:
                        response["id"] = str(message["id"])
                    else:
                        response["id"] = "0"  # fallback
                
                # stdout으로 응답 출력
                print(json.dumps(response), flush=True)
                
            except json.JSONDecodeError as e:
                debug_log("JSON decode error:", e)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": "0",  # null 대신 문자열 사용
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)
                
            except Exception as e:
                debug_log("Error processing message:", str(e))
                
                # 원본 메시지에서 id 추출 시도
                msg_id = "0"
                try:
                    msg = json.loads(line)
                    if "id" in msg:
                        msg_id = str(msg["id"])
                except:
                    pass
                
                error_response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                }
                print(json.dumps(error_response), flush=True)
    
    except KeyboardInterrupt:
        debug_log("Proxy interrupted")
    
    debug_log("Proxy closed")


if __name__ == "__main__":
    main()