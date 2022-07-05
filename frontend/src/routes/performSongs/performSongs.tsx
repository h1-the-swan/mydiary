import React, { useEffect } from "react";
import { PerformSongRead, useReadPerformSongsList } from "../../api";
import { Table, TableColumnType } from "antd";

function PerformSongTable() {
  const { data: performSongs, isLoading } = useReadPerformSongsList(
    { limit: 5000 },
    {
      query: {
        select: (d) => d.data,
      },
    }
  );
  useEffect(() => console.log(performSongs), [performSongs]);
  const columns: TableColumnType<PerformSongRead>[] = [
    {
      title: "id",
      dataIndex: "id",
      key: "id",
      sorter: (a, b) => a.id - b.id,
    },
    {
      title: "Name",
      dataIndex: "name",
      key: "name",
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: "Artist",
      dataIndex: "artist_name",
      key: "artist",
      sorter: (a, b) => a.artist_name.localeCompare(b.artist_name),
    },
    {
      title: "Learned",
      dataIndex: "learned",
      key: "learned",
      render: (value: boolean) => Number(value),
      sorter: (a, b) => Number(a.learned) - Number(b.learned),
    },
    {
      title: "Spotify ID",
      dataIndex: "spotify_id",
      key: "spotify_id",
    },
    {
      title: "Key",
      dataIndex: "key",
      key: "key",
    },
    {
      title: "Capo",
      dataIndex: "capo",
      key: "capo",
    },
//     {
//       title: "Played At",
//       dataIndex: "played_at",
//       key: "played_at",
//       render: (value: string) => {
//         const dt = new Date(value + "Z");
//         return dt.toLocaleString();
//       },
//       sorter: (a, b) =>
//         new Date(a.played_at + "Z").getTime() -
//         new Date(b.played_at + "Z").getTime(),
//     },
//     {
//       title: "context_name",
//       dataIndex: "context_name",
//       key: "context_name",
//       render: (value, record) => (
//         <a href={record.context_uri} target="_blank" rel="noreferrer">
//           {value}
//         </a>
//       ),
//       sorter: true,
//     },
  ];
  return isLoading ? (
    <span>Loading...</span>
  ) : (
    <Table
      dataSource={performSongs}
      columns={columns}
      pagination={{ pageSize: 100 }}
    />
  );
}

const PerformSongs = () => {
  return (
    <main>
      <PerformSongTable />
    </main>
  );
};

export { PerformSongs };

