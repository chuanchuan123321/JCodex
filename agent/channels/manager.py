"""Channel manager for coordinating chat channels."""

import asyncio
from contextlib import suppress

from agent.bus.queue import MessageBus
from agent.channels.base import BaseChannel
from agent.config.schema import Config


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Feishu, Telegram, etc.)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None

        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize channels based on config."""

        # Feishu channel
        if self.config.channels.feishu.enabled:
            try:
                from agent.channels.feishu import FeishuChannel

                self.channels["feishu"] = FeishuChannel(
                    self.config.channels.feishu, self.bus
                )
                print("✅ Feishu channel enabled")
            except ImportError as e:
                print(f"⚠️  Feishu channel not available: {e}")

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            print("⚠️  No channels enabled")
            return

        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # Start all channels
        tasks = []
        for name, channel in self.channels.items():
            print(f"🚀 Starting {name} channel...")
            tasks.append(asyncio.create_task(channel.start()))

        # Wait for all to complete (they should run forever)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        print("🛑 Stopping all channels...")

        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._dispatch_task

        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                print(f"✅ Stopped {name} channel")
            except Exception as e:
                print(f"❌ Error stopping {name}: {e}")

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        print("📤 Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(), timeout=1.0
                )

                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        print(f"❌ Error sending to {msg.channel}: {e}")
                else:
                    print(f"⚠️  Unknown channel: {msg.channel}")

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
