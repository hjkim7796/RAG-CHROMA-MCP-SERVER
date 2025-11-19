#!/usr/bin/env python3
"""
MCP HTTP Proxy (Python)
stdio를 HTTP/SSE로 변환하는 프록시
"""

import sys
import json
import requests

# 설정
SERVER_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/sse"
DEBUG = True  # 프로덕션에서는 False로 설정


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
                'Accept': 'application/json'
            },
            timeout=60
        )
        
        response.raise_for_status()
        
        debug_log(f"Response status: {response.status_code}")
        debug_log(f"Response headers: {dict(response.headers)}")
        
        # JSON 응답 파싱
        result = response.json()
        debug_log("Received JSON response:", json.dumps(result))
        
        # 응답 검증
        if not isinstance(result, dict):
            raise Exception(f"Invalid response type: {type(result)}")
        
        # jsonrpc 필드 확인
        if "jsonrpc" not in result:
            result["jsonrpc"] = "2.0"
        
        # id 필드 확인 및 설정
        if "id" not in result or result["id"] is None:
            if "id" in message:
                result["id"] = str(message["id"])
            else:
                result["id"] = "0"
        
        return result
            
    except requests.exceptions.Timeout:
        raise Exception("Request timed out - server may not be responding")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Connection refused - is the server running at {SERVER_URL}?")
    except requests.exceptions.HTTPError as e:
        error_text = e.response.text[:200] if hasattr(e.response, 'text') else str(e)
        raise Exception(f"HTTP error {e.response.status_code}: {error_text}")
    except json.JSONDecodeError as e:
        raise Exception(f"Invalid JSON response: {str(e)}")
    except Exception as e:
        debug_log("Request error:", str(e))
        raise


def create_error_response(message_id, code, error_message):
    """에러 응답 생성"""
    return {
        "jsonrpc": "2.0",
        "id": str(message_id) if message_id is not None else "0",
        "error": {
            "code": code,
            "message": error_message
        }
    }


def main():
    """메인 함수"""
    debug_log(f"MCP HTTP Proxy started, connecting to: {SERVER_URL}")
    
    try:
        # stdin에서 한 줄씩 읽기
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            message_id = None
            
            try:
                # JSON 메시지 파싱
                message = json.loads(line)
                debug_log("Received from stdin:", json.dumps(message))
                
                # id 추출
                message_id = message.get("id")
                
                # id를 문자열로 변환
                if message_id is not None:
                    message["id"] = str(message_id)
                
                # HTTP 요청 전송 및 응답 받기
                response = send_http_request(message)
                
                # 응답 검증
                if not response:
                    response = create_error_response(
                        message_id,
                        -32603,
                        "Empty response from server"
                    )
                elif "error" not in response and "result" not in response:
                    # result나 error가 없으면 에러 응답으로 변환
                    debug_log("Warning: Response missing 'result' or 'error', treating as error")
                    response = create_error_response(
                        message_id,
                        -32603,
                        f"Invalid response format: {json.dumps(response)}"
                    )
                
                # 응답의 id를 문자열로 변환
                if "id" in response and response["id"] is not None:
                    response["id"] = str(response["id"])
                elif message_id is not None:
                    response["id"] = str(message_id)
                
                # stdout으로 응답 출력
                print(json.dumps(response), flush=True)
                
            except json.JSONDecodeError as e:
                debug_log("JSON decode error:", e)
                error_response = create_error_response(
                    message_id,
                    -32700,
                    f"Parse error: {str(e)}"
                )
                print(json.dumps(error_response), flush=True)
                
            except Exception as e:
                debug_log("Error processing message:", str(e))
                
                error_response = create_error_response(
                    message_id,
                    -32603,
                    str(e)
                )
                print(json.dumps(error_response), flush=True)
    
    except KeyboardInterrupt:
        debug_log("Proxy interrupted")
    
    debug_log("Proxy closed")


if __name__ == "__main__":
    main()