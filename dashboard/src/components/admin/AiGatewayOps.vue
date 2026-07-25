<template>
	<div class="space-y-4">
		<div class="rounded-lg border border-gray-200 bg-white p-8 text-center">
			<p class="text-sm font-semibold text-gray-900">Gateway performance — coming next</p>
			<p class="mx-auto mt-2 max-w-lg text-xs leading-relaxed text-gray-500">
				This view will show throughput (req/min), latency p50/p95, error &amp; retry rate, worker
				concurrency, and a latency breakdown (gateway vs model vs tool) to pinpoint bottlenecks —
				plus tool-build candidates (jobs with the most tool calls). It needs a one-time enablement
				of the LiteLLM Prometheus callback on the gateway.
			</p>
		</div>
	</div>
</template>

<script>
export default { name: 'AiGatewayOps' };
</script>
