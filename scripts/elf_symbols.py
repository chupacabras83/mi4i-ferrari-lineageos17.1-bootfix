import sys
from elftools.elf.elffile import ELFFile
for f in sys.argv[1:]:
    e=ELFFile(open(f,'rb'))
    d=e.get_section_by_name('.dynamic')
    print('==',f.split('/')[-1], 'NEEDED:',[t.needed for t in d.iter_tags() if t.entry.d_tag=='DT_NEEDED'])
    s=e.get_section_by_name('.dynsym')
    ex=[x.name for x in s.iter_symbols() if x.entry.st_shndx!='SHN_UNDEF' and x['st_info']['type']=='STT_FUNC']
    print(' exports(wifi/init):',sorted(n for n in ex if 'wifi' in n.lower() or 'init' in n.lower())[:40])
