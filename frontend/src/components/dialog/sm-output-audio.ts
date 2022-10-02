import { createMachine, send, type AnyEventObject, type InvokeCallback } from "xstate";
import { busConnector, EventBus } from "../eventBus";
import { PlaybackRequestMessage } from "./messages";
import { eventNameForMessageType, eventNameForProtocolName } from "./sm-helpers";


export type Context = {
    eventBus: EventBus,
};

const runPlayback = (_: Context, evt: AnyEventObject): InvokeCallback<any, AnyEventObject> => (callback, _) => {
    const request = PlaybackRequestMessage.parse(evt.data);

    const interval = setInterval(
        () => {
            callback({ type: 'TICK', data: { playbackId: request.playbackId } });
        },
        1000
    );

    const el = new Audio(request.url);

    el.setAttribute('data-playback-id', request.playbackId);
    el.style.display = 'none';
    el.addEventListener('ended', () => {
        callback({ type: 'DONE', data: { playbackId: request.playbackId } });
    });
    el.addEventListener('error', () => {
        callback({ type: 'ERROR', data: { playbackId: request.playbackId } });
    });

    const parent = document.getElementsByTagName('body')[0];

    parent.appendChild(el);

    el.play();

    return () => {
        clearInterval(interval);
        parent.removeChild(el);
    }
};

export const audioOutputMachine = createMachine<Context>(
    {
        id: 'audioOutput',
        predictableActionArguments: true,
        initial: 'inactive',
        invoke: {
            id: 'eventBus',
            src: 'eventBus',
        },
        states: {
            inactive: {
                on: {
                    [eventNameForProtocolName('out.audio.link')]: {
                        target: 'active',
                    },
                },
            },
            active: {
                on: {
                    WS_DISCONNECTED: {
                        target: 'inactive',
                    },
                },
                initial: 'waiting',
                states: {
                    waiting: {
                        on: {
                            [eventNameForMessageType('out.audio.link/playback-request')]: {
                                actions: ['storeToHistory'],
                                target: 'playing',
                            },
                        },
                    },
                    playing: {
                        invoke: {
                            id: 'playback',
                            src: 'runPlayback',
                        },
                        entry: ['sendPlaybackStart'],
                        exit: ['sendPlaybackEnd'],
                        on: {
                            TICK: {
                                actions: ['sendProgressMessage']
                            },
                            DONE: {
                                actions: ['sendDoneMessage'],
                                target: 'waiting',
                            },
                            ERROR: {
                                actions: ['sendDoneMessage'],
                                target: 'waiting',
                            },
                        },
                    },
                },
            },
        },
    },
    {
        services: {
            eventBus: busConnector([
                eventNameForProtocolName('out.audio.link'),
                eventNameForMessageType('out.audio.link/playback-request'),
                'WS_DISCONNECTED',
            ]),
            runPlayback,
        },
        actions: {
            sendProgressMessage: send(
                (_, event) => ({ type: 'WS_SEND', data: { type: 'out.audio.link/playback-progress', playbackId: event.data.playbackId } }),
                { to: 'eventBus' }
            ),
            sendDoneMessage: send(
                (_, event) => ({ type: 'WS_SEND', data: { type: 'out.audio.link/playback-done', playbackId: event.data.playbackId } }),
                { to: 'eventBus' }
            ),
            sendPlaybackStart: send(
                () => ({ type: 'PLAYBACK_STARTED' }),
                { to: 'eventBus' }
            ),
            sendPlaybackEnd: send(
                () => ({ type: 'PLAYBACK_ENDED' }),
                { to: 'eventBus' }
            ),
            storeToHistory: send(
                (_, event) => ({
                    type: 'HISTORY_ADD_MESSAGE',
                    data: { direction: 'out', text: PlaybackRequestMessage.parse(event.data).altText ?? '🔊' }
                }),
                { to: 'eventBus' }
            ),
        },
    }
);
