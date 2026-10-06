<Stack gap="sm" p="sm">
  <Group justify="space-between"><Text fw={700}>Media &amp; node storage</Text><RefreshButton /></Group>
  {status.capacity?.loading ? <Skeleton height={100} /> : status.capacity?.error ? <Alert color="red" title="Storage unavailable">SABnzbd could not report the media filesystem. Refresh to retry.</Alert> : data.capacity?.queue?.diskspacetotal1 > 0 ? <Stack gap="xs">
    <Text size="xl" fw={700} c={data.capacity.queue.diskspace1 / data.capacity.queue.diskspacetotal1 < 0.1 ? "red" : "teal"}>{data.capacity.queue.diskspace1} GiB free</Text>
    <Progress value={(1 - data.capacity.queue.diskspace1 / data.capacity.queue.diskspacetotal1) * 100} color={data.capacity.queue.diskspace1 / data.capacity.queue.diskspacetotal1 < 0.1 ? "red" : "orange"} />
    <Text size="sm" c="dimmed">{data.capacity.queue.diskspacetotal1} GiB total</Text>
    <Text size="xs" c="dimmed">Shared media and download filesystem</Text>
  </Stack> : <Alert color="yellow" title="No capacity reported">Check that the media filesystem is mounted in SABnzbd.</Alert>}
  <Divider />
  {status.node?.error ? <Text size="xs" c="red">Proxmox system disk unavailable</Text> : data.node?.data?.rootfs?.total > 0 ? <Stack gap={4}>
    <Text size="xs" c="dimmed">Proxmox system disk · {Math.round(data.node.data.rootfs.avail / 1073741824 * 10) / 10} GiB free / {Math.round(data.node.data.rootfs.total / 1073741824 * 10) / 10} GiB</Text>
    <Progress size="xs" value={data.node.data.rootfs.used / data.node.data.rootfs.total * 100} color={data.node.data.rootfs.avail / data.node.data.rootfs.total < 0.1 ? "red" : "blue"} />
  </Stack> : <Text size="xs" c="dimmed">Loading Proxmox system disk…</Text>}
</Stack>
