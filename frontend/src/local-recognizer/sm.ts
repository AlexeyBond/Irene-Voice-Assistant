import { eventNameForMessageType, eventNameForProtocolName } from "@/components/dialog/sm-helpers";
import { assign, createMachine, send, type AnyEventObject, type InvokeCallback } from "xstate";
import { busConnector, type EventBus } from "@/components/eventBus";

export type Context = {
    eventBus: EventBus,
    sampleRate: number,
    error?: Error,
};

export const localRecognizerStateMachine = createMachine<Context>(
    {
        id: 'localRecognizer',
        predictableActionArguments: true,
        invoke: {
            id: 'eventBus',
            src: 'eventBus',
        },
        initial: 'inactive',
        states: {
            inactive: {
                on: {
                    [eventNameForProtocolName('in.text-indirect')]: { target: 'active.indirect' },
                    [eventNameForProtocolName('in.stt.clientside')]: { target: 'active.sttClientSide' },
                },
            },
            active: {
                invoke: {
                    src: 'runRecognition',
                    id: 'recognizer',
                },
                on: {
                    WS_DISCONNECTED: { target: 'inactive' },
                    ERROR: {
                        target: 'error',
                        actions: ['storeError'],
                    },
                    PLAYBACK_STARTED: { actions: ['forwardToRecognizer'] },
                    PLAYBACK_ENDED: { actions: ['forwardToRecognizer'] },
                },
                states: {
                    indirect: {
                        on: {
                            RECOGNIZED: {
                                actions: ['sendIndirectText'],
                            },
                            [eventNameForProtocolName('in.stt.clientside')]: {
                                target: 'sttClientSide'
                            },
                        },
                    },
                    sttClientSide: {
                        on: {
                            RECOGNIZED: {
                                actions: ['sendSTTInput'],
                            },
                            [eventNameForMessageType('in.stt.clientside/processed')]: {
                                actions: ['forwardProcessedToHistory'],
                            },
                        },
                    },
                },
            },
            error: {
                tags: ['error']
            },
        },
    },
    {
        services: {
            eventBus: busConnector([
                eventNameForProtocolName('in.text-indirect'),
                eventNameForProtocolName('in.stt.clientside'),
                'WS_DISCONNECTED',
                eventNameForMessageType('in.stt.clientside/processed'),
                'PLAYBACK_STARTED',
                'PLAYBACK_ENDED',
            ]),
            runRecognition: (context: Context): InvokeCallback<AnyEventObject, AnyEventObject> => (callback, onReceived) => {
                const p: Promise<() => Promise<void>> = (async () => {
                    const { run } = await import('@/local-recognizer/voskService');
                    let cb;

                    try {
                        cb = await run({
                            sampleRate: context.sampleRate,
                            onRecognized: text => callback({ type: 'RECOGNIZED', data: text }),
                            onReceived,
                        });
                    } catch (e) {
                        callback({ type: 'ERROR', data: e });
                        throw e;
                    }

                    return cb;
                })();

                return async () => {
                    console.log('Останавливаю распознаватель');
                    let cb;
                    try {
                        cb = await p;
                    } catch (e) {
                        return;
                    }

                    cb();
                };
            },
        },
        actions: {
            sendIndirectText: send(
                (_, evt) => ({ type: 'WS_SEND', data: { type: 'in.text-indirect/text', text: evt.data } }),
                { to: 'eventBus' },
            ),
            sendSTTInput: send(
                (_, evt) => ({ type: 'WS_SEND', data: { type: 'in.stt.clientside/recognized', text: evt.data } }),
                { to: 'eventBus' },
            ),
            forwardProcessedToHistory: send(
                (_, evt) => ({ type: 'HISTORY_ADD_MESSAGE', data: { direction: 'in', text: evt.data.text } }),
                { to: 'eventBus' },
            ),
            storeError: assign({
                error: (_, event) => event.data,
            }),
            forwardToRecognizer: send(
                (_, evt) => evt,
                { to: 'recognizer' },
            ),
        },
    },
);
