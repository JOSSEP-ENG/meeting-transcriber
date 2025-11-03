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
      transcription_recorded: [],  // 추가: 화자 정보 포함된 녹취 기록
      speaker_mapping_required: [],  // 추가: 화자 매핑 요청
      speaker_mapped: [],  // 추가: 화자 매핑 완료
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
   * @param {string} options.language - 언어 코드 (기본값: ko-KR)
   * @param {string} options.speaker - 화자 이름
   * @param {string} options.meeting_title - 회의 제목
   * @param {string} options.participants - 참석자 명단 (쉼표로 구분)
   */
  startRecording({ language = 'ko-KR', speaker = '', meeting_title = '', participants = '' } = {}) {
    if (!this.isConnected) {
      throw new Error('WebSocket이 연결되지 않았습니다');
    }

    const message = {
      type: 'start',
      language,
      speaker,
      meeting_title,
      participants,  // 추가
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
   * 일반 메시지 전송
   * @param {object} message - 메시지 객체
   */
  send(message) {
    if (!this.isConnected) {
      throw new Error('WebSocket이 연결되지 않았습니다');
    }

    this.ws.send(JSON.stringify(message));
  }

  /**
   * 오디오 데이터 전송 (Base64)
   * @param {string} audioBase64 - Base64 인코딩된 오디오 데이터
   */
  sendAudio(audioBase64) {
    this.send({
      type: 'audio',
      data: audioBase64,
    });
  }


  /**
   * 화자 매핑 전송
   * @param {number} speakerId - Speaker ID
   * @param {string} speakerName - 화자 이름
   */
  sendSpeakerMapping(speakerId, speakerName) {
    this.send({
      type: 'speaker_mapping',
      speaker_id: speakerId,
      speaker_name: speakerName,
    });
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
