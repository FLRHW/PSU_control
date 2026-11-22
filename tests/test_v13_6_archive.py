"""No PSU access: archive retention is opt-in, verified and no-clobber."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from cpx400dp_archive import gather, archive


class ArchiveTests(unittest.TestCase):
    def test_companion_folder_console_and_csv_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            raw=root/'test_measurements_123.csv'
            report=root/'test_report_123.html'
            console=root/'test_console_123.log'
            side=root/'test_report_123_data'
            side.mkdir()
            raw.write_text('event,channel\nreadback,1\n')
            report.write_text('<html>synthetic report</html>')
            console.write_text('dry-run console')
            (side/'c1_000000.js').write_text('synthetic data')
            originals={p:p.read_bytes() for p in
                       (raw,report,console,side/'c1_000000.js')}
            target=root/'bundle.zip'
            result=archive(raw,target)
            self.assertEqual(result,target)
            with zipfile.ZipFile(result) as z:
                names=set(z.namelist())
                self.assertEqual(names,{
                    'test_measurements_123.csv','test_report_123.html',
                    'test_console_123.log','test_report_123_data/c1_000000.js',
                    'MANIFEST.json'})
                manifest=json.loads(z.read('MANIFEST.json'))
                self.assertEqual(len(manifest['files']),4)
                for p,b in originals.items():
                    self.assertEqual(z.read(p.relative_to(root).as_posix()), b)
            self.assertTrue(all(p.read_bytes()==b for p,b in originals.items()))
            with self.assertRaises(FileExistsError):
                archive(raw,target)
            self.assertEqual(target.read_bytes(),result.read_bytes())

    def test_raw_only_log_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            raw=Path(directory)/'p_measurements.csv'
            raw.write_text('test')
            with zipfile.ZipFile(archive(raw)) as z:
                self.assertEqual(set(z.namelist()),
                                 {raw.name,'MANIFEST.json'})

    def test_avoids_archive_symlink_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            raw=base/'a_measurements.csv'
            raw.write_text('test')
            secret=base/'secret.txt'
            secret.write_text('external')
            (base/'a_report.html').symlink_to(secret)
            with self.assertRaises(ValueError):
                gather(raw)

    def test_missing_raw_file_or_bad_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'wrong.csv';p.write_text('x')
            with self.assertRaisesRegex(ValueError,'_measurements'):
                archive(p)
            with self.assertRaises(FileNotFoundError):
                archive(Path(directory)/'missing_measurements.csv')


if __name__=='__main__':
    unittest.main()
