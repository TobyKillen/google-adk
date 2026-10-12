"""Enable A2UI button actions to continue the current ADK Web chat session.

ADK Web's A2UI buttons build userAction payloads, but the stock chat component
does not route them to the active session. This compatibility patch forwards
button actions from the renderer to ChatComponent.sendMessage without introducing
a separate web app or changing the agent transport.

Run this after installing or upgrading google-adk and before `adk web`.
"""

from __future__ import annotations

import sys
import re
from importlib.metadata import version
from pathlib import Path


PATCH_MARKER = "A2UI_WEB_ACTION_BRIDGE_V2"
OLD_PATCH_MARKER = "A2UI_WEB_ACTION_BRIDGE_V1"
CHAT_CONSTRUCTOR = (
    "constructor(){Ir(()=>{this.themeService?.currentTheme()&&"
    "this.updateRenderedGraph()})}ngOnInit(){"
)
PATCHED_CHAT_CONSTRUCTOR = (
    "constructor(){/* A2UI_WEB_ACTION_BRIDGE_V2 */"
    "this.a2uiActionHandler=e=>{const a=e.detail;"
    "if(!a)return;"
    "this.sendMessage({role:'user',parts:[{text:'A2UI userAction: '+JSON.stringify(a)}]});"
    "};window.addEventListener('adk-a2ui-action',this.a2uiActionHandler);"
    "Ir(()=>{this.themeService?.currentTheme()&&this.updateRenderedGraph()})}ngOnInit(){"
)
CHAT_CONSTRUCTOR_V1 = (
    "constructor(){/* A2UI_WEB_ACTION_BRIDGE_V1 */"
    "this.a2uiActionSubscription=C(W5).events.subscribe(({message:e,completion:i})=>{"
    "const a=e?.userAction;"
    "if(!a){i?.next({status:'ignored'});return}"
    "this.sendMessage({role:'user',parts:[{text:'A2UI userAction: '+JSON.stringify(a)}]});"
    "i?.next({status:'sent'})"
    "});"
    "Ir(()=>{this.themeService?.currentTheme()&&this.updateRenderedGraph()})}ngOnInit(){"
)
CHAT_DESTROY = "ngOnDestroy(){this.handleStopMessage(),this.streamChatService.closeStream()}"
PATCHED_CHAT_DESTROY = (
    "ngOnDestroy(){window.removeEventListener('adk-a2ui-action',this.a2uiActionHandler),"
    "this.handleStopMessage(),this.streamChatService.closeStream()}"
)
CHAT_DESTROY_V1 = (
    "ngOnDestroy(){this.a2uiActionSubscription?.unsubscribe(),"
    "this.handleStopMessage(),this.streamChatService.closeStream()}"
)
ACTION_DISPATCH = (
    "let a={userAction:{name:e.name,sourceComponentId:i.id,surfaceId:r,"
    "timestamp:new Date().toISOString(),context:o}};return this.processor.dispatch(a)"
)
PATCHED_ACTION_DISPATCH = (
    "let a={userAction:{name:e.name,sourceComponentId:i.id,surfaceId:r,"
    "timestamp:new Date().toISOString(),context:o}};"
    "window.dispatchEvent(new CustomEvent('adk-a2ui-action',{detail:a.userAction}));"
    "return this.processor.dispatch(a)"
)


def main() -> int:
    adk_version = version("google-adk")
    if adk_version != "2.11.0":
        print(
            f"This patch targets google-adk 2.11.0; found {adk_version}. "
            "Review the ADK Web bundle before adapting the patch.",
            file=sys.stderr,
        )
        return 2

    import google.adk.cli

    browser_dir = Path(google.adk.cli.__file__).parent / "browser"
    bundles = list(browser_dir.glob("main-*.js"))
    if len(bundles) != 1:
        print(
            f"Expected one ADK Web main bundle in {browser_dir}; found {len(bundles)}.",
            file=sys.stderr,
        )
        return 2

    bundle = bundles[0]
    source = bundle.read_text(encoding="utf-8")
    if PATCH_MARKER not in source:
        if OLD_PATCH_MARKER in source:
            if source.count(CHAT_CONSTRUCTOR_V1) != 1 or source.count(CHAT_DESTROY_V1) != 1:
                print("Found an incomplete v1 bridge; no files were changed.", file=sys.stderr)
                return 2
            source = source.replace(CHAT_CONSTRUCTOR_V1, PATCHED_CHAT_CONSTRUCTOR, 1)
            source = source.replace(CHAT_DESTROY_V1, PATCHED_CHAT_DESTROY, 1)
        else:
            if source.count(CHAT_CONSTRUCTOR) != 1:
                print(
                    "Could not locate the expected ADK Web chat constructor. "
                    "No files were changed.",
                    file=sys.stderr,
                )
                return 2
            if source.count(CHAT_DESTROY) != 1:
                print(
                    "Could not locate the expected ADK Web chat teardown. "
                    "No files were changed.",
                    file=sys.stderr,
                )
                return 2
            source = source.replace(CHAT_CONSTRUCTOR, PATCHED_CHAT_CONSTRUCTOR, 1)
            source = source.replace(CHAT_DESTROY, PATCHED_CHAT_DESTROY, 1)

        if source.count(ACTION_DISPATCH) != 1:
            print(
                "Could not locate the expected ADK Web A2UI action dispatcher. "
                "No files were changed.",
                file=sys.stderr,
            )
            return 2
        source = source.replace(ACTION_DISPATCH, PATCHED_ACTION_DISPATCH, 1)
        bundle.write_text(source, encoding="utf-8")

    index = browser_dir / "index.html"
    html = index.read_text(encoding="utf-8")
    cache_busted_tag = f'src="./{bundle.name}?a2ui_action_bridge=2" type="module"'
    script_pattern = re.compile(
        rf'src="\./{re.escape(bundle.name)}(?:\?[^"]*)?" type="module"'
    )
    if len(script_pattern.findall(html)) != 1:
        print(
            "Could not locate the ADK Web entry script in index.html.",
            file=sys.stderr,
        )
        return 2
    html = script_pattern.sub(cache_busted_tag, html, count=1)
    index.write_text(html, encoding="utf-8")

    print(f"A2UI action bridge is installed for ADK Web 2.11.0 in {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
