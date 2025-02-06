import { eventNameForMessageType } from '@/components/dialog/sm-helpers';
import type { AnyEventObject, Receiver } from 'xstate';

const createMediaStream = ({ sampleRate }: { sampleRate: number }): Promise<MediaStream> => {
    if (!navigator?.mediaDevices?.getUserMedia) {
        throw new Error("Голосовой ввод не поддерживается");
    }

    return navigator.mediaDevices.getUserMedia({
        video: false,
        audio: {
            echoCancellation: true,
            noiseSuppression: true,
            channelCount: 1,
            sampleRate,
        },
    });
};

/**
 * Отключает микрофон в переданном `MediaStream` во время воспроизведения аудио на этом клиенте или где-то в другом месте.
 * 
 * Предотвращает распознание речи голосового ассистента в качестве пользовательского ввода.
 * 
 * Использует сообщения, отправляемые сервером по протоколу `in.mute`.
 */
const processMuteRequests = ({ onReceived, mediaStream, context }: { onReceived: Receiver<AnyEventObject>, mediaStream: MediaStream, context: AudioContext }) => {
    onReceived(event => {
        const track = mediaStream.getTracks()[0];

        if (!track) {
            return;
        }

        switch (event.type) {
            case eventNameForMessageType('in.mute/mute'):
                context.suspend();
                break;
            case eventNameForMessageType('in.mute/unmute'):
                context.resume();
        }
    });
};


export const run = async ({
    sampleRate = 48000,
    gain = 1.0,
    onReceived = () => { },
    sendChunk,
}: {
    sampleRate?: number,
    gain?: number,
    onReceived: Receiver<AnyEventObject>,
    sendChunk: (chunk: ArrayBuffer) => void
}) => {
    let terminate: (() => Promise<void> | void) | null = null;

    try {
        const mediaStream = await createMediaStream({ sampleRate });

        const terminateStream = () => {
            for (const track of mediaStream.getTracks()) {
                track.stop();
            }
        }

        terminate = terminateStream;

        const audioContext = new AudioContext();

        const terminateContext = () => audioContext.close();

        terminate = async () => {
            await terminateContext();
            terminateStream();
        }

        const source = audioContext.createMediaStreamSource(mediaStream);

        const scriptProcessor = audioContext.createScriptProcessor(1024, 1, 1);

        scriptProcessor.onaudioprocess = event => {
            const inputFloats = event.inputBuffer.getChannelData(0);

            const inputShorts = new Int16Array(inputFloats.length);

            function convert(n: number) {
                var v = n < 0 ? n * 32768 : n * 32767;
                return Math.max(-32768, Math.min(32767, v));
            }

            for (let i = 0; i < inputFloats.length; ++i) {
                inputShorts[i] = convert(inputFloats[i]);
            }

            sendChunk(inputShorts.buffer);
        }

        const gainNode = audioContext.createGain();
        gainNode.gain.value = gain;

        source.connect(gainNode);
        gainNode.connect(scriptProcessor);

        scriptProcessor.connect(audioContext.destination);

        processMuteRequests({ onReceived, mediaStream, context: audioContext });
    } catch (e) {
        try {
            await terminate?.();
        } catch (ee) {
            console.error(ee);
        }

        throw e;
    }


    return terminate;
}

export const streamingSupported = (() => {
    let supported = false;
    const ac = new AudioContext();

    try {

        supported = !!ac.createScriptProcessor(1024);
    } catch (error) {
        console.warn(error);
    } finally {
        ac.close();
    }

    if (!supported) {
        console.warn("Потоковый ввод аудио не поддерживается");
    }

    return supported;
})();
