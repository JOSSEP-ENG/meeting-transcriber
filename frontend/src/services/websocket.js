/**
 * WebSocket 서비스
 * 백엔드 WebSocket 서버와 통신하여 실시간 회의 녹음 기능 제공
 */

class WebSocketService {
  constructor() {
    this.ws = null;
    this.isConnected = false;
    this.sessionId = null;
    this.messageHandlers = {
      status: [],
      transcription_received: [],
      completed: [],
      error: [],
    };
  }

  /**
   * WebSocket 서버에 연결
   * @param {string} url - WebSocket 서버 URL (기본값: ws://localhost:8000/ws/record)
   */
  connect(url = 'ws://localhost:8000/ws/record') {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log('WebSocket 연결됨');
          this.isConnected = true;
          resolve();
        };

        this.ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          this._handleMessage(data);
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket 에러:', error);
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('WebSocket 연결 종료');
          this.isConnected = false;
          this.sessionId = null;
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 서버로부터 받은 메시지 처리
   * @param {object} data - 메시지 데이터
   */
  _handleMessage(data) {
    const { type } = data;
    console.log('메시지 수신:', type, data);

    if (type === 'status' && data.session_id) {
      this.sessionId = data.session_id;
    }

    // 등록된 핸들러 실행
    const handlers = this.messageHandlers[type] || [];
    handlers.forEach((handler) => handler(data));
  }

  /**
   * 메시지 타입별 핸들러 등록
   * @param {string} type - 메시지 타입 (status, transcription_received, completed, error)
   * @param {function} handler - 핸들러 함수
   */
  on(type, handler) {
    if (!this.messageHandlers[type]) {
      this.messageHandlers[type] = [];
    }
    this.messageHandlers[type].push(handler);
  }

  /**
   * 핸들러 제거
   * @param {string} type - 메시지 타입
   * @param {function} handler - 제거할 핸들러 함수
   */
  off(type, handler) {
    if (this.messageHandlers[type]) {
      this.messageHandlers[type] = this.messageHandlers[type].filter(
        (h) => h !== handler
      );
    }
  }

  /**
   * 회의 녹음 시작
   * @param {object} options - 녹음 옵션
   * @param {string} options.language - 언어 코드 (기본값: ko)
   * @param {string} options.speaker - 화자 이름
   * @param {string} options.meeting_title - 회의 제목
   */
  startRecording({ language = 'ko', speaker = '', meeting_title = '' } = {}) {
    if (!this.isConnected) {
      throw new Error('WebSocket이 연결되지 않았습니다');
    }

    const message = {
      type: 'start',
      language,
      speaker,
      meeting_title,
    };

    this.ws.send(JSON.stringify(message));
    console.log('녹음 시작 요청:', message);
  }

  /**
   * 음성 인식된 텍스트 전송
   * @param {string} text - 변환된 텍스트
   */
  sendTranscription(text) {
    if (!this.isConnected) {
      throw new Error('WebSocket이 연결되지 않았습니다');
    }

    const message = {
      type: 'transcription',
      text,
    };

    this.ws.send(JSON.stringify(message));
    console.log('텍스트 전송:', text);
  }

  /**
   * 회의 녹음 종료
   */
  endRecording() {
    if (!this.isConnected) {
      throw new Error('WebSocket이 연결되지 않았습니다');
    }

    const message = {
      type: 'end',
    };

    this.ws.send(JSON.stringify(message));
    console.log('녹음 종료 요청');
  }

  /**
   * WebSocket 연결 종료
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
      this.isConnected = false;
      this.sessionId = null;
    }
  }
}

export default new WebSocketService();
